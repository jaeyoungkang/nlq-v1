"""
Query Processing Service - SQL 쿼리 전담 처리 (순수화)
"""

import logging
from typing import Dict, Any, List
from .models import QueryRequest, QueryResult
from models import ContextBlock, BlockType, context_blocks_to_llm_format

logger = logging.getLogger(__name__)


class QueryProcessingService:
    """쿼리 처리 서비스 - ContextBlock 기반"""
    
    def __init__(self, llm_client, bigquery_client):
        self.llm_client = llm_client
        self.bigquery_client = bigquery_client
    
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
            
            # SQL 생성 (ContextBlock 직접 전달)
            sql_result = self.llm_client.generate_sql(
                request.query, 
                self.bigquery_client.project_id, 
                None, 
                context_blocks
            )
            
            if not sql_result["success"]:
                request.context_block.status = "failed"
                request.context_block.error_info = {"error": sql_result.get('error')}
                return QueryResult(
                    success=False,
                    result_type="query_result",
                    context_block=request.context_block,
                    error=sql_result.get('error')
                )
            
            generated_sql = sql_result["sql"]
            logger.info("⚡ 쿼리 실행 중...")
            
            # 쿼리 실행
            query_result = self.bigquery_client.execute_query(generated_sql)
            
            # ContextBlock 업데이트 (단순화)
            request.context_block.assistant_response = f"쿼리 실행 완료: {query_result.get('row_count', 0)}개 행 반환"
            
            if query_result.get("success"):
                request.context_block.execution_result = {
                    "data": query_result.get("data", []),
                    "row_count": query_result.get("row_count", 0),
                    "generated_sql": generated_sql,
                    "execution_time_ms": query_result.get("stats", {}).get("execution_time_ms"),
                    "bytes_processed": query_result.get("stats", {}).get("bytes_processed")
                }
                request.context_block.status = "completed"
            else:
                request.context_block.status = "failed"
            
            return QueryResult(
                success=query_result.get("success", False),
                result_type="query_result",
                context_block=request.context_block,
                data=query_result.get("data", []),
                generated_sql=generated_sql,
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
    
