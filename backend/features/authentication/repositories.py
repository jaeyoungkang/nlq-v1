"""
Authentication Repository
인증 관련 데이터 접근 계층 - 화이트리스트 검증, 세션 관리
"""

from typing import Dict, Any, Optional
from core.repositories.base import BaseRepository, bigquery, NotFound
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class AuthRepository(BaseRepository):
    """인증 관련 데이터 접근 계층"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        super().__init__(
            table_name="user_sessions", 
            dataset_name="v1", 
            project_id=project_id, 
            location=location
        )
    
    def check_user_whitelist(self, email: str, user_id: str) -> Dict[str, Any]:
        """사용자 화이트리스트 검증"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            # 화이트리스트 테이블에서 사용자 확인
            whitelist_table_id = f"{self.project_id}.{self.dataset_name}.users_whitelist"
            
            query = f"""
            SELECT user_id, email, status, created_at
            FROM `{whitelist_table_id}`
            WHERE email = @email
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig()
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter('email', 'STRING', email)
            ]
            
            try:
                query_job = self.client.query(query, job_config=job_config)
                results = query_job.result()
                
                user_data = None
                for row in results:
                    user_data = {
                        'user_id': row.user_id,
                        'email': row.email,
                        'status': row.status,
                        'created_at': row.created_at
                    }
                    break
                
                if not user_data:
                    return {
                        'success': True,
                        'allowed': False,
                        'message': '접근이 허용되지 않은 계정입니다',
                        'reason': 'not_whitelisted'
                    }
                
                # 상태에 따른 접근 확인
                if user_data['status'] == 'active':
                    # 로그인 시간 업데이트
                    try:
                        self._update_last_login(email)
                    except Exception as e:
                        logger.warning(f"로그인 시간 업데이트 실패: {email}, 오류: {str(e)}")
                    
                    return {
                        'success': True,
                        'allowed': True,
                        'message': '접근 허용',
                        'user_data': user_data
                    }
                elif user_data['status'] == 'pending':
                    return {
                        'success': True,
                        'allowed': False,
                        'message': '계정 승인이 대기 중입니다',
                        'reason': 'pending_approval',
                        'status': 'pending'
                    }
                else:
                    return {
                        'success': True,
                        'allowed': False,
                        'message': '계정이 비활성화되었습니다',
                        'reason': 'account_disabled',
                        'status': user_data['status']
                    }
                    
            except NotFound:
                return {
                    'success': False,
                    'error': '화이트리스트 테이블을 찾을 수 없습니다'
                }
            
        except Exception as e:
            logger.error(f"화이트리스트 검증 중 예외: {str(e)}")
            return {'success': False, 'error': f'화이트리스트 검증 오류: {str(e)}'}
    
    def link_session_to_user(self, session_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """세션을 사용자에게 연결"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            # 대화 테이블에서 해당 세션의 대화들을 사용자에게 연결
            conversations_table_id = f"{self.project_id}.{self.dataset_name}.conversations"
            
            # 임시 세션 ID로 저장된 대화들을 실제 사용자 ID로 업데이트
            update_query = f"""
            UPDATE `{conversations_table_id}`
            SET user_id = @user_id
            WHERE user_id = @session_id
            """
            
            job_config = bigquery.QueryJobConfig()
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter('user_id', 'STRING', user_id),
                bigquery.ScalarQueryParameter('session_id', 'STRING', session_id)
            ]
            
            try:
                query_job = self.client.query(update_query, job_config=job_config)
                query_job.result()  # 쿼리 완료 대기
                
                # 업데이트된 행 수 확인
                updated_rows = query_job.num_dml_affected_rows or 0
                
                return {
                    'success': True,
                    'updated_rows': updated_rows,
                    'message': f'{updated_rows}개의 대화가 계정에 연결되었습니다'
                }
                
            except Exception as e:
                logger.error(f"세션 연결 쿼리 실행 중 오류: {str(e)}")
                return {
                    'success': False,
                    'error': f'세션 연결 쿼리 실패: {str(e)}',
                    'updated_rows': 0
                }
            
        except Exception as e:
            logger.error(f"세션 연결 중 오류: {str(e)}")
            return {'success': False, 'error': f'세션 연결 실패: {str(e)}'}
    
    def _update_last_login(self, email: str) -> None:
        """사용자 마지막 로그인 시간 업데이트"""
        try:
            whitelist_table_id = f"{self.project_id}.{self.dataset_name}.users_whitelist"
            
            # 먼저 updated_at 컬럼이 존재하는지 확인
            table = self.client.get_table(whitelist_table_id)
            has_updated_at = any(field.name == 'updated_at' for field in table.schema)
            
            if has_updated_at:
                update_query = f"""
                UPDATE `{whitelist_table_id}`
                SET updated_at = CURRENT_TIMESTAMP()
                WHERE email = @email
                """
                
                job_config = bigquery.QueryJobConfig()
                job_config.query_parameters = [
                    bigquery.ScalarQueryParameter('email', 'STRING', email)
                ]
                
                query_job = self.client.query(update_query, job_config=job_config)
                query_job.result()
                
                logger.debug(f"로그인 시간 업데이트 완료: {email}")
            else:
                logger.debug(f"updated_at 컬럼이 없어 로그인 시간 업데이트 건너뜀: {email}")
            
        except Exception as e:
            logger.warning(f"로그인 시간 업데이트 실패: {email}, 오류: {str(e)}")
            # 로그인 시간 업데이트 실패는 로그인 자체를 막지 않음
            pass