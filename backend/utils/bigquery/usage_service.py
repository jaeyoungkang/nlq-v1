"""
BigQuery 사용량 서비스
사용량 추적, 통계, 관리자 기능 담당
"""

import os
import logging
from typing import Dict, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)

class UsageService:
    """BigQuery 사용량 관리 서비스"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        UsageService 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        try:
            self.client = bigquery.Client(project=project_id, location=location)
            logger.info(f"BigQuery UsageService 초기화 완료: {project_id}")
        except Exception as e:
            logger.error(f"BigQuery UsageService 초기화 실패: {str(e)}")
            raise
    
    def get_usage_count(self, session_id: str, ip_address: str) -> Dict[str, Any]:
        """
        비인증 사용자의 일일 사용량 조회 (개선된 버전)
        
        Args:
            session_id: 세션 ID
            ip_address: IP 주소
            
        Returns:
            사용량 정보
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            
            # 테이블 존재 확인
            try:
                table_ref = self.client.dataset(dataset_name).table('usage_tracking')
                self.client.get_table(table_ref)
            except NotFound:
                logger.warning(f"⚠️ 사용량 추적 테이블이 존재하지 않습니다: {usage_table}")
                # 테이블이 없으면 기본값 반환
                return {
                    "success": True,
                    "daily_count": 0,
                    "remaining": 10,
                    "table_missing": True
                }
            
            query = f"""
            SELECT daily_count, last_request
            FROM `{usage_table}`
            WHERE session_id = @session_id 
              AND ip_address = @ip_address
              AND date_key = CURRENT_DATE()
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                    bigquery.ScalarQueryParameter("ip_address", "STRING", ip_address)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            daily_count = results[0].daily_count if results else 0
            daily_limit = int(os.getenv('DAILY_USAGE_LIMIT', '10'))
            
            return {
                "success": True,
                "daily_count": daily_count,
                "remaining": max(0, daily_limit - daily_count),
                "daily_limit": daily_limit,
                "last_request": results[0].last_request.isoformat() if results and results[0].last_request else None
            }
            
        except Exception as e:
            logger.error(f"사용량 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "daily_count": 0,
                "remaining": 10  # 오류 시 안전한 기본값
            }
    
    def update_usage_count(self, session_id: str, ip_address: str, user_agent: str = "") -> Dict[str, Any]:
        """
        비인증 사용자의 사용량 업데이트 (개선된 버전)
        
        Args:
            session_id: 세션 ID
            ip_address: IP 주소
            user_agent: 브라우저 정보
            
        Returns:
            업데이트 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            
            # 테이블 존재 확인
            try:
                table_ref = self.client.dataset(dataset_name).table('usage_tracking')
                self.client.get_table(table_ref)
            except NotFound:
                logger.warning(f"⚠️ 사용량 추적 테이블이 존재하지 않습니다: {usage_table}")
                return {
                    "success": False,
                    "error": "사용량 추적 테이블이 존재하지 않습니다",
                    "table_missing": True
                }
            
            # User-Agent 길이 제한
            if len(user_agent) > 1000:
                user_agent = user_agent[:1000]
            
            # MERGE 문을 사용하여 업데이트 또는 삽입
            query = f"""
            MERGE `{usage_table}` T
            USING (
              SELECT 
                @session_id as session_id,
                @ip_address as ip_address,
                @user_agent as user_agent,
                CURRENT_DATE() as date_key,
                CURRENT_TIMESTAMP() as last_request
            ) S
            ON T.session_id = S.session_id 
              AND T.ip_address = S.ip_address 
              AND T.date_key = S.date_key
            WHEN MATCHED THEN
              UPDATE SET 
                daily_count = T.daily_count + 1,
                last_request = S.last_request,
                user_agent = S.user_agent
            WHEN NOT MATCHED THEN
              INSERT (session_id, ip_address, user_agent, daily_count, last_request, date_key)
              VALUES (S.session_id, S.ip_address, S.user_agent, 1, S.last_request, S.date_key)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                    bigquery.ScalarQueryParameter("ip_address", "STRING", ip_address),
                    bigquery.ScalarQueryParameter("user_agent", "STRING", user_agent)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            logger.info(f"사용량 업데이트 완료: {session_id} ({ip_address})")
            return {
                "success": True,
                "updated_count": 1
            }
            
        except Exception as e:
            logger.error(f"사용량 업데이트 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_usage_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        사용량 통계 조회 (관리자용)
        
        Args:
            days: 조회 일수
            
        Returns:
            사용량 통계
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            
            # 대화 통계
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            conversations_stats = self._get_conversation_statistics(conversations_table, days)
            
            # 사용량 통계
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            usage_stats = self._get_usage_tracking_statistics(usage_table, days)
            
            return {
                "success": True,
                "period_days": days,
                "conversations": conversations_stats,
                "usage_tracking": usage_stats
            }
            
        except Exception as e:
            logger.error(f"사용량 통계 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_conversation_statistics(self, table_name: str, days: int) -> Dict[str, Any]:
        """대화 통계 조회"""
        try:
            query = f"""
            SELECT 
              COUNT(*) as total_messages,
              COUNT(DISTINCT conversation_id) as total_conversations,
              COUNT(DISTINCT user_id) as authenticated_users,
              COUNT(DISTINCT session_id) as guest_sessions,
              COUNT(CASE WHEN message_type = 'user' THEN 1 END) as user_messages,
              COUNT(CASE WHEN message_type = 'assistant' THEN 1 END) as ai_responses,
              COUNT(CASE WHEN is_authenticated = true THEN 1 END) as auth_messages,
              COUNT(CASE WHEN is_authenticated = false THEN 1 END) as guest_messages
            FROM `{table_name}`
            WHERE DATE(timestamp) >= CURRENT_DATE() - @days
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                return {
                    'total_messages': row.total_messages,
                    'total_conversations': row.total_conversations,
                    'authenticated_users': row.authenticated_users,
                    'guest_sessions': row.guest_sessions,
                    'user_messages': row.user_messages,
                    'ai_responses': row.ai_responses,
                    'auth_messages': row.auth_messages,
                    'guest_messages': row.guest_messages
                }
            else:
                return {'error': 'No data found'}
                
        except Exception as e:
            logger.error(f"대화 통계 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    def _get_usage_tracking_statistics(self, table_name: str, days: int) -> Dict[str, Any]:
        """사용량 추적 통계 조회"""
        try:
            query = f"""
            SELECT 
              COUNT(DISTINCT session_id) as unique_sessions,
              SUM(daily_count) as total_requests,
              AVG(daily_count) as avg_requests_per_session,
              MAX(daily_count) as max_requests_per_session,
              COUNT(DISTINCT date_key) as active_days
            FROM `{table_name}`
            WHERE date_key >= CURRENT_DATE() - @days
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                return {
                    'unique_sessions': row.unique_sessions,
                    'total_requests': row.total_requests,
                    'avg_requests_per_session': float(row.avg_requests_per_session) if row.avg_requests_per_session else 0,
                    'max_requests_per_session': row.max_requests_per_session,
                    'active_days': row.active_days
                }
            else:
                return {'error': 'No usage data found'}
                
        except Exception as e:
            logger.error(f"사용량 추적 통계 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_usage_data(self, retention_days: int = 90) -> Dict[str, Any]:
        """
        오래된 사용량 데이터 정리
        
        Args:
            retention_days: 보존 기간 (일)
            
        Returns:
            정리 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            
            # 오래된 데이터 삭제
            query = f"""
            DELETE FROM `{usage_table}`
            WHERE date_key < CURRENT_DATE() - @retention_days
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("retention_days", "INT64", retention_days)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            deleted_rows = query_job.num_dml_affected_rows or 0
            
            logger.info(f"사용량 데이터 정리 완료: {deleted_rows}행 삭제 (보존기간: {retention_days}일)")
            
            return {
                "success": True,
                "deleted_rows": deleted_rows,
                "retention_days": retention_days,
                "message": f"{retention_days}일 이전 사용량 데이터 {deleted_rows}행이 삭제되었습니다"
            }
            
        except Exception as e:
            logger.error(f"사용량 데이터 정리 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }