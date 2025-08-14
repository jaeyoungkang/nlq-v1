"""
BigQuery 쿼리 서비스
쿼리 실행 담당
"""

import logging
from datetime import datetime
from typing import Dict, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, BadRequest, Forbidden

logger = logging.getLogger(__name__)

class QueryService:
    """BigQuery 쿼리 실행 서비스"""
    
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