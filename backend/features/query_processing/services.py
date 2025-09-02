"""
Query Processing Service - SQL 쿼리 전담 처리 (순수화)
"""

from typing import Dict, Any, List
from .models import QueryRequest, QueryResult
from core.models import ContextBlock, BlockType, context_blocks_to_llm_format
from utils.logging_utils import get_logger
from features.llm.models import SQLGenerationRequest
from google.cloud import bigquery
import os

logger = get_logger(__name__)


class QueryProcessingService:
    """쿼리 처리 서비스 - ContextBlock 기반 (단순화)"""
    
    def __init__(self, llm_service, chat_repository=None):
        self.llm_service = llm_service
        self.chat_repository = chat_repository  # ContextBlock 저장용으로만 사용
        # BigQuery는 직접 연결 (쿼리 실행용)
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.bigquery_client = bigquery.Client(project=self.project_id) if self.project_id else None
    
    def process_sql_query(self, request: QueryRequest, context_blocks: List[ContextBlock] = None) -> QueryResult:
        """
        SQL 쿼리 처리 - 순수화된 기능
        
        Args:
            request: 쿼리 요청 (ContextBlock 포함)
            context_blocks: 이전 대화 컨텍스트 (ContextBlock 리스트)
            
        Returns:
            QueryResult: SQL 쿼리 처리 결과
        """
        # ContextBlock 상태를 processing으로 변경
        request.context_block.status = "processing"
        request.context_block.block_type = BlockType.QUERY
        
        try:
            return self._process_sql_query(request, context_blocks or [])
                
        except Exception as e:
            logger.error(f"SQL 쿼리 처리 중 오류: {str(e)}")
            
            # ContextBlock 에러 상태 업데이트
            request.context_block.status = "failed"
            
            return QueryResult(
                success=False,
                result_type="error",
                context_block=request.context_block,
                error=str(e)
            )
    
    def _process_sql_query(self, request: QueryRequest, context_blocks: List[ContextBlock]) -> QueryResult:
        """SQL 쿼리 처리 - ContextBlock 업데이트"""
        try:
            logger.info("📝 SQL 생성 중...")
            
            # SQL 생성 - ContextBlock 직접 전달
            sql_request = SQLGenerationRequest(
                user_question=request.query,
                project_id=self.project_id or 'nlq-ex',
                default_table='nlq-ex.test_dataset.events_20210131',
                context_blocks=context_blocks
            )
            
            sql_response = self.llm_service.generate_sql(sql_request)
            generated_sql = sql_response.sql_query
            logger.info("⚡ 쿼리 실행 중...")
            
            # 쿼리 실행 (BigQuery 직접 연결)
            query_result = self._execute_bigquery(generated_sql)
            
            # ContextBlock 업데이트 (단순화)
            request.context_block.assistant_response = f"쿼리 실행 완료: {query_result.get('row_count', 0)}개 행 반환"
            request.context_block.generated_query = generated_sql  # 별도 필드로 설정
            
            if query_result.get("success"):
                request.context_block.execution_result = {
                    "data": query_result.get("data", []),
                    "row_count": query_result.get("row_count", 0)
                }
                request.context_block.status = "completed"
            else:
                request.context_block.status = "failed"
            
            return QueryResult(
                success=query_result.get("success", False),
                result_type="query_result",
                context_block=request.context_block,
                data=query_result.get("data", []),
                generated_query=generated_sql,
                row_count=query_result.get("row_count", 0),
                error=query_result.get("error")
            )
            
        except Exception as e:
            logger.error(f"SQL 쿼리 처리 중 오류: {str(e)}")
            request.context_block.status = "failed"
            return QueryResult(
                success=False,
                result_type="query_result",
                context_block=request.context_block,
                error=str(e)
            )
    
    def _execute_bigquery(self, sql_query: str) -> Dict[str, Any]:
        """
        BigQuery 쿼리 직접 실행
        
        Args:
            sql_query: 실행할 SQL 쿼리
            
        Returns:
            실행 결과 딕셔너리
        """
        try:
            if not self.bigquery_client:
                return {"success": False, "error": "BigQuery 클라이언트가 초기화되지 않았습니다", "data": [], "row_count": 0}
            
            logger.info(f"BigQuery 쿼리 실행 중: {sql_query[:100]}...")
            
            # 쿼리 실행
            query_job = self.bigquery_client.query(sql_query)
            results = query_job.result()
            
            # 결과 데이터 변환
            data = []
            for row in results:
                row_dict = dict(row)
                # BigQuery의 특수 타입들을 JSON 직렬화 가능한 형태로 변환
                for key, value in row_dict.items():
                    if hasattr(value, 'isoformat'):  # datetime 객체
                        row_dict[key] = value.isoformat()
                    elif value is None:
                        continue
                data.append(row_dict)
            
            row_count = len(data)
            logger.info(f"BigQuery 쿼리 실행 완료: {row_count}개 행")
            
            return {
                "success": True,
                "data": data,
                "row_count": row_count,
                "message": f"쿼리가 성공적으로 실행되었습니다 ({row_count}개 행)"
            }
            
        except Exception as e:
            logger.error(f"BigQuery 쿼리 실행 실패: {str(e)}")
            return {
                "success": False, 
                "error": str(e),
                "data": [],
                "row_count": 0
            }
    
