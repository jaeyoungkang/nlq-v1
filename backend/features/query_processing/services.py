"""
Query Processing Service - SQL 쿼리 전담 처리 (순수화)
"""

from typing import Dict, Any, List
from .models import QueryRequest, QueryResult
from .repositories import QueryProcessingRepository
from core.models import ContextBlock, BlockType, context_blocks_to_llm_format
from utils.logging_utils import get_logger
from features.llm.models import SQLGenerationRequest

logger = get_logger(__name__)


class QueryProcessingService:
    """쿼리 처리 서비스 - ContextBlock 기반"""
    
    def __init__(self, llm_service, query_processing_repository=None):
        self.llm_service = llm_service
        self.repository = query_processing_repository or QueryProcessingRepository()
        # 하위 호환성을 위해 project_id 접근 가능하게 함
        self.project_id = self.repository.project_id if self.repository else None
    
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
            
            # 쿼리 실행
            query_result = self.repository.execute_query(generated_sql)
            
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
    
