"""
BigQuery 쿼리 서비스
쿼리 실행, 검증, 메타데이터 조회 담당
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, BadRequest, Forbidden

logger = logging.getLogger(__name__)

class QueryService:
    """BigQuery 쿼리 실행 및 메타데이터 관리 서비스"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        QueryService 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        try:
            self.client = bigquery.Client(project=project_id, location=location)
            logger.info(f"BigQuery QueryService 초기화 완료: {project_id} (리전: {location})")
        except Exception as e:
            logger.error(f"BigQuery QueryService 초기화 실패: {str(e)}")
            raise
    
    def execute_query(self, sql_query: str, max_results: int = 1000) -> Dict[str, Any]:
        """
        BigQuery에서 SQL 쿼리 실행
        
        Args:
            sql_query: 실행할 SQL 쿼리
            max_results: 최대 결과 행 수
            
        Returns:
            실행 결과 딕셔너리
        """
        try:
            logger.info(f"쿼리 실행 시작: {sql_query[:100]}...")
            
            # 쿼리 작업 설정
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=10**10,  # 10GB 제한
                use_query_cache=True
            )
            
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # 결과 대기 (타임아웃 30초)
            results = query_job.result(timeout=30, max_results=max_results)
            
            # 결과를 딕셔너리 리스트로 변환
            rows = []
            for row in results:
                row_dict = {}
                for key, value in zip(row.keys(), row.values()):
                    # 날짜/시간 객체를 문자열로 변환
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                    elif hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                    else:
                        row_dict[key] = value
                rows.append(row_dict)
            
            # 쿼리 통계 수집
            stats = self._extract_job_stats(query_job)
            
            logger.info(f"쿼리 실행 완료: {len(rows)}행 반환")
            
            return {
                "success": True,
                "data": rows,
                "row_count": len(rows),
                "stats": stats
            }
            
        except BadRequest as e:
            logger.error(f"잘못된 쿼리: {str(e)}")
            return {
                "success": False,
                "error": f"SQL 문법 오류: {str(e)}",
                "error_type": "syntax_error"
            }
            
        except Forbidden as e:
            logger.error(f"권한 오류: {str(e)}")
            return {
                "success": False,
                "error": f"접근 권한이 없습니다: {str(e)}",
                "error_type": "permission_error"
            }
            
        except NotFound as e:
            logger.error(f"리소스 없음: {str(e)}")
            return {
                "success": False,
                "error": f"테이블 또는 데이터셋을 찾을 수 없습니다: {str(e)}",
                "error_type": "not_found"
            }
            
        except Exception as e:
            logger.error(f"쿼리 실행 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"쿼리 실행 실패: {str(e)}",
                "error_type": "execution_error"
            }
    
    def validate_query(self, sql_query: str) -> Dict[str, Any]:
        """
        SQL 쿼리 문법 검증 (실행하지 않음)
        
        Args:
            sql_query: 검증할 SQL 쿼리
            
        Returns:
            검증 결과
        """
        try:
            # 드라이 런으로 쿼리 검증
            job_config = bigquery.QueryJobConfig(
                dry_run=True,
                use_query_cache=False
            )
            
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # 예상 비용 계산 (TB당 $5 기준)
            bytes_processed = query_job.total_bytes_processed or 0
            tb_processed = bytes_processed / (1024**4)
            estimated_cost = tb_processed * 5
            
            return {
                "success": True,
                "valid": True,
                "bytes_processed": bytes_processed,
                "tb_processed": round(tb_processed, 6),
                "estimated_cost_usd": round(estimated_cost, 4),
                "message": "쿼리가 유효합니다"
            }
            
        except BadRequest as e:
            return {
                "success": True,
                "valid": False,
                "error": str(e),
                "message": "쿼리에 문법 오류가 있습니다"
            }
            
        except Exception as e:
            logger.error(f"쿼리 검증 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"검증 중 오류 발생: {str(e)}"
            }
    
    def list_datasets(self) -> Dict[str, Any]:
        """
        프로젝트의 데이터셋 목록 조회
        
        Returns:
            데이터셋 목록
        """
        try:
            datasets = list(self.client.list_datasets())
            
            dataset_list = []
            for dataset in datasets:
                dataset_info = {
                    "dataset_id": dataset.dataset_id,
                    "full_dataset_id": f"{self.project_id}.{dataset.dataset_id}",
                    "description": dataset.description or "",
                    "location": dataset.location or "US"
                }
                dataset_list.append(dataset_info)
            
            return {
                "success": True,
                "datasets": dataset_list,
                "count": len(dataset_list)
            }
            
        except Exception as e:
            logger.error(f"데이터셋 목록 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "datasets": []
            }
    
    def list_tables(self, dataset_id: str) -> Dict[str, Any]:
        """
        데이터셋의 테이블 목록 조회
        
        Args:
            dataset_id: 데이터셋 ID
            
        Returns:
            테이블 목록
        """
        try:
            dataset_ref = self.client.dataset(dataset_id)
            tables = list(self.client.list_tables(dataset_ref))
            
            table_list = []
            for table in tables:
                table_info = {
                    "table_id": table.table_id,
                    "full_table_id": f"{self.project_id}.{dataset_id}.{table.table_id}",
                    "table_type": table.table_type,
                    "created": table.created.isoformat() if table.created else None
                }
                table_list.append(table_info)
            
            return {
                "success": True,
                "tables": table_list,
                "count": len(table_list)
            }
            
        except NotFound:
            return {
                "success": False,
                "error": f"데이터셋 '{dataset_id}'를 찾을 수 없습니다",
                "tables": []
            }
            
        except Exception as e:
            logger.error(f"테이블 목록 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tables": []
            }
    
    def get_table_schema(self, dataset_id: str, table_id: str) -> Dict[str, Any]:
        """
        테이블 스키마 정보 조회
        
        Args:
            dataset_id: 데이터셋 ID
            table_id: 테이블 ID
            
        Returns:
            스키마 정보
        """
        try:
            table_ref = self.client.dataset(dataset_id).table(table_id)
            table = self.client.get_table(table_ref)
            
            schema_fields = []
            for field in table.schema:
                field_info = {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                }
                schema_fields.append(field_info)
            
            return {
                "success": True,
                "table_id": f"{self.project_id}.{dataset_id}.{table_id}",
                "schema": schema_fields,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None
            }
            
        except NotFound:
            return {
                "success": False,
                "error": f"테이블 '{dataset_id}.{table_id}'를 찾을 수 없습니다"
            }
            
        except Exception as e:
            logger.error(f"스키마 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_default_table_metadata(self) -> dict:
        """기본 테이블의 메타데이터 조회"""
        default_table = "nlq-ex.test_dataset.events_20210131"
        
        try:
            table = self.client.get_table(default_table)
            
            # 기본 정보
            table_info = {
                "table_id": default_table,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "size_mb": round((table.num_bytes or 0) / (1024 * 1024), 2),
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
                "description": table.description or ""
            }
            
            # 스키마 정보
            schema = []
            for field in table.schema:
                schema.append({
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                })
            
            return {
                "success": True,
                "table_info": table_info,
                "schema": schema
            }
            
        except Exception as e:
            logger.error(f"기본 테이블 메타데이터 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "table_info": {"table_id": default_table},
                "schema": []
            }
    
    def format_bytes(self, bytes_count: int) -> str:
        """바이트 수를 읽기 쉬운 형태로 포맷"""
        if bytes_count == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(bytes_count)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
    def _extract_job_stats(self, query_job) -> Dict[str, Any]:
        """쿼리 작업 통계 추출"""
        try:
            return {
                "job_id": query_job.job_id,
                "bytes_processed": query_job.total_bytes_processed,
                "bytes_billed": query_job.total_bytes_billed,
                "slot_ms": getattr(query_job, 'slot_millis', None),
                "creation_time": query_job.created.isoformat() if hasattr(query_job, 'created') and query_job.created else None,
                "start_time": query_job.started.isoformat() if hasattr(query_job, 'started') and query_job.started else None,
                "end_time": query_job.ended.isoformat() if hasattr(query_job, 'ended') and query_job.ended else None,
                "cache_hit": getattr(query_job, 'cache_hit', False),
                "state": getattr(query_job, 'state', None)
            }
        except Exception as e:
            logger.warning(f"통계 추출 중 오류: {str(e)}")
            return {
                "job_id": getattr(query_job, 'job_id', 'unknown'),
                "error": str(e)
            }