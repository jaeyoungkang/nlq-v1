"""
Query Processing Repository
쿼리 실행 결과 저장 및 조회를 담당하는 리포지토리
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from core.repositories.base import BaseRepository, bigquery
from utils.logging_utils import get_logger
from .models import QueryRequest, QueryResult
from core.models import ContextBlock

logger = get_logger(__name__)


class QueryProcessingRepository(BaseRepository):
    """쿼리 실행 결과를 저장하고 조회하는 리포지토리"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        """
        QueryProcessingRepository 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        super().__init__(
            table_name="query_results",
            dataset_name="v1",
            project_id=project_id,
            location=location
        )
        self.bigquery_client = None
    
    def set_bigquery_client(self, bigquery_client):
        """BigQuery 클라이언트 설정"""
        self.bigquery_client = bigquery_client
    
    def ensure_table_exists(self) -> Dict[str, Any]:
        """query_results 테이블 존재 확인 및 생성 (ContextBlock 호환)"""
        try:
            dataset_ref = self.client.dataset(self.dataset_name)
            
            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
            except bigquery.NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "NLQ-v1 query results dataset"
                self.client.create_dataset(dataset)
                logger.info(f"데이터셋 생성: {self.dataset_name}")
            
            # 테이블 확인/생성
            table_ref = dataset_ref.table(self.table_name)
            try:
                self.client.get_table(table_ref)
                return {"success": True, "action": "exists", "table_id": self.table_id}
            except bigquery.NotFound:
                # ContextBlock과 호환되는 확장된 스키마로 테이블 생성
                schema = [
                    # ContextBlock 기본 필드
                    bigquery.SchemaField("block_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"), 
                    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("block_type", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_request", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("assistant_response", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("execution_result", "JSON", mode="NULLABLE"),
                    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                    
                    # QueryResult 확장 필드 (호환성)
                    bigquery.SchemaField("query_id", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("user_query", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("generated_query", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("result_data", "JSON", mode="NULLABLE"),
                    bigquery.SchemaField("result_row_count", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("result_status", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("execution_time_ms", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("bytes_processed", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("cache_hit", "BOOLEAN", mode="NULLABLE"),
                    bigquery.SchemaField("metadata", "JSON", mode="NULLABLE")
                ]
                
                table = bigquery.Table(table_ref, schema=schema)
                table.description = "Query processing results with ContextBlock compatibility"
                self.client.create_table(table)
                
                logger.info(f"query_results 테이블 생성 완료: {self.table_id}")
                return {"success": True, "action": "created", "table_id": self.table_id}
                
        except Exception as e:
            logger.error(f"query_results 테이블 확인/생성 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def execute_query(self, sql_query: str, max_results: int = 1000) -> Dict[str, Any]:
        """
        SQL 쿼리 직접 실행
        
        Args:
            sql_query: 실행할 SQL 쿼리
            max_results: 최대 결과 행 수
            
        Returns:
            쿼리 실행 결과 딕셔너리
        """
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            import time
            start_time = time.time()
            
            # BigQuery 쿼리 실행
            job_config = bigquery.QueryJobConfig()
            job_config.use_query_cache = True
            job_config.use_legacy_sql = False
            
            query_job = self.client.query(sql_query, job_config=job_config)
            results = query_job.result(max_results=max_results)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # 결과를 딕셔너리 리스트로 변환
            data = []
            for row in results:
                row_dict = {}
                for key, value in row.items():
                    # BigQuery 타입을 JSON 직렬화 가능한 타입으로 변환
                    if hasattr(value, 'isoformat'):  # datetime 객체
                        row_dict[key] = value.isoformat()
                    elif hasattr(value, '__float__'):  # Decimal 등
                        row_dict[key] = float(value)
                    else:
                        row_dict[key] = value
                data.append(row_dict)
            
            # 쿼리 통계 정보
            stats = {
                "execution_time_ms": execution_time_ms,
                "bytes_processed": query_job.total_bytes_processed,
                "bytes_billed": query_job.total_bytes_billed,
                "cache_hit": query_job.cache_hit
            }
            
            return {
                'success': True,
                'data': data,
                'row_count': len(data),
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"쿼리 실행 중 오류: {str(e)}")
            return {'success': False, 'error': f'쿼리 실행 실패: {str(e)}'}
    
    def save_query_result(self, 
                         request: QueryRequest, 
                         result: QueryResult,
                         execution_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        쿼리 실행 결과 저장
        
        Args:
            request: 쿼리 요청
            result: 쿼리 결과
            execution_stats: 실행 통계 정보
            
        Returns:
            저장 결과 딕셔너리
        """
        try:
            query_id = result.context_block.block_id if result.context_block else str(uuid.uuid4())
            current_time = datetime.now(timezone.utc)
            
            # 결과 데이터 직렬화
            result_data_json = None
            if result.data:
                result_data_json = json.dumps(result.data)
            
            # 메타데이터 구성
            metadata = {
                'result_type': result.result_type,
                'context_block_id': result.context_block.block_id if result.context_block else None
            }
            
            # 저장할 데이터 구성
            data = {
                'query_id': query_id,
                'user_id': request.user_id,
                'user_query': request.query,
                'generated_query': result.generated_sql,
                'result_data': result_data_json,
                'result_row_count': result.row_count,
                'result_status': 'success' if result.success else 'failed',
                'error_message': result.error,
                'timestamp': current_time.isoformat(),
                'execution_time_ms': execution_stats.get('execution_time_ms') if execution_stats else None,
                'bytes_processed': execution_stats.get('bytes_processed') if execution_stats else None,
                'cache_hit': execution_stats.get('cache_hit') if execution_stats else None,
                'metadata': json.dumps(metadata)
            }
            
            # BaseRepository의 save 메서드 사용
            save_result = self.save(data)
            
            if save_result.get('success'):
                logger.info(f"쿼리 결과 저장 완료: {query_id}")
                return {
                    "success": True,
                    "query_id": query_id,
                    "message": "쿼리 결과가 성공적으로 저장되었습니다"
                }
            else:
                return save_result
                
        except Exception as e:
            logger.error(f"쿼리 결과 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}