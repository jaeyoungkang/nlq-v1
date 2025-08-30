"""
Authentication Service
인증 관련 비즈니스 로직 계층
"""

import hashlib
from typing import Dict, Any
from utils.token_utils import TokenHandler
from utils.time_utils import TimeManager
from utils.logging_utils import get_logger
from .repositories import AuthRepository

logger = get_logger(__name__)


class AuthService:
    """인증 비즈니스 로직 계층"""
    
    def __init__(self, token_handler: TokenHandler, auth_repository: AuthRepository):
        self.token_handler = token_handler
        self.auth_repository = auth_repository
        self.active_sessions = {}
    
    def authenticate_google_user(self, id_token: str) -> Dict[str, Any]:
        """Google ID 토큰 검증 및 사용자 인증"""
        try:
            # Google 토큰 검증
            token_result = self.token_handler.verify_google_token(id_token)
            if not token_result['success']:
                return token_result
            
            # 화이트리스트 검증
            user_info = token_result['user_info']
            whitelist_result = self.auth_repository.check_user_whitelist(
                user_info['email'], user_info['user_id']
            )
            
            if not whitelist_result['success']:
                return {
                    'success': False,
                    'error': '사용자 권한 확인 중 오류가 발생했습니다',
                    'error_type': 'whitelist_check_failed'
                }
            
            if not whitelist_result['allowed']:
                return {
                    'success': False,
                    'error': whitelist_result.get('message', '접근이 허용되지 않은 사용자입니다'),
                    'error_type': 'access_denied',
                    'reason': whitelist_result.get('reason'),
                    'user_status': whitelist_result.get('status')
                }
            
            token_result['whitelist_data'] = whitelist_result.get('user_data', {})
            return token_result
            
        except Exception as e:
            logger.error(f"Google 사용자 인증 중 오류: {str(e)}")
            return {'success': False, 'error': f'인증 처리 실패: {str(e)}'}
    
    def generate_user_session(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 세션 생성 및 JWT 토큰 발급"""
        try:
            token_result = self.token_handler.generate_jwt_tokens(user_info)
            if not token_result['success']:
                return token_result
            
            # 세션 저장
            session_id = self._generate_session_id(user_info['user_id'])
            session_data = {
                'user_info': user_info,
                'created_at': TimeManager.utc_datetime_string(),
                'last_activity': TimeManager.utc_datetime_string()
            }
            
            self.active_sessions[session_id] = session_data
            return token_result
            
        except Exception as e:
            logger.error(f"사용자 세션 생성 중 오류: {str(e)}")
            return {'success': False, 'error': f'세션 생성 실패: {str(e)}'}
    
    def refresh_user_token(self, refresh_token: str) -> Dict[str, Any]:
        """리프레시 토큰으로 새로운 액세스 토큰 발급"""
        return self.token_handler.refresh_access_token(refresh_token)
    
    def verify_user_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """JWT 토큰 검증"""
        return self.token_handler.verify_jwt_token(token, token_type)
    
    def logout_user(self, user_id: str) -> Dict[str, Any]:
        """사용자 로그아웃"""
        try:
            sessions_to_remove = [
                session_id for session_id, session_data in self.active_sessions.items()
                if session_data['user_info']['user_id'] == user_id
            ]
            
            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]
            
            return {
                'success': True,
                'message': '성공적으로 로그아웃되었습니다',
                'removed_sessions': len(sessions_to_remove)
            }
            
        except Exception as e:
            logger.error(f"로그아웃 중 오류: {str(e)}")
            return {'success': False, 'error': f'로그아웃 실패: {str(e)}'}
    
    def link_session_to_user(self, session_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """세션을 사용자에게 연결"""
        return self.auth_repository.link_session_to_user(session_id, user_id, user_email)
    
    def _generate_session_id(self, user_id: str) -> str:
        """세션 ID 생성"""
        current_timestamp = int(TimeManager.utc_now().timestamp())
        session_data = f"{user_id}:{current_timestamp}"
        return hashlib.md5(session_data.encode()).hexdigest()