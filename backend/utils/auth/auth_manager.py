"""
인증 관리자 핵심 클래스
사용자 세션 관리 - 로그인 사용자만 지원
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from .token_handler import TokenHandler
from ..time_utils import TimeManager

logger = logging.getLogger(__name__)

class AuthManager:
    """인증 관리 클래스 - 로그인 사용자만 지원"""
    
    def __init__(self):
        """인증 관리자 초기화"""
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        
        # 토큰 처리기 초기화
        self.token_handler = TokenHandler(
            google_client_id=self.google_client_id,
            jwt_secret=self.jwt_secret
        )
        
        # 인증된 사용자 세션 저장소 (메모리 기반)
        self.active_sessions = {}  # {session_id: user_info}
        
        if not self.google_client_id or not self.jwt_secret:
            logger.warning("⚠️ Google Client ID 또는 JWT Secret이 설정되지 않았습니다")
    
    def verify_google_token(self, id_token_str: str) -> Dict[str, Any]:
        """Google ID 토큰 검증 (토큰 핸들러에 위임)"""
        return self.token_handler.verify_google_token(id_token_str)
    
    def generate_jwt_tokens(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """JWT 토큰 생성 (토큰 핸들러에 위임)"""
        token_result = self.token_handler.generate_jwt_tokens(user_info)
        
        if token_result['success']:
            # 세션 저장
            session_id = self._generate_session_id(user_info['user_id'])
            self.active_sessions[session_id] = {
                'user_info': user_info,
                'created_at': TimeManager.utc_datetime_string(),
                'last_activity': TimeManager.utc_datetime_string()
            }
        
        return token_result
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """리프레시 토큰으로 새로운 액세스 토큰 발급 (토큰 핸들러에 위임)"""
        return self.token_handler.refresh_access_token(refresh_token)
    
    def verify_jwt_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """JWT 토큰 검증 (토큰 핸들러에 위임)"""
        return self.token_handler.verify_jwt_token(token, token_type)
    
    def logout_user(self, user_id: str) -> Dict[str, Any]:
        """
        사용자 로그아웃 (세션 제거)
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            로그아웃 결과
        """
        try:
            # 해당 사용자의 모든 세션 제거
            sessions_to_remove = []
            for session_id, session_data in self.active_sessions.items():
                if session_data['user_info']['user_id'] == user_id:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]
            
            logger.info(f"👋 사용자 로그아웃: {user_id} ({len(sessions_to_remove)}개 세션 제거)")
            
            return {
                'success': True,
                'message': '성공적으로 로그아웃되었습니다',
                'removed_sessions': len(sessions_to_remove)
            }
            
        except Exception as e:
            logger.error(f"❌ 로그아웃 중 오류: {str(e)}")
            return {
                'success': False,
                'error': f'로그아웃 실패: {str(e)}'
            }

    def cleanup_expired_sessions(self):
        """만료된 세션 정리 (표준화된 시간 사용)"""
        try:
            current_time = TimeManager.utc_now()
            refresh_token_expires = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000))  # 30일
            expired_sessions = []
            
            for session_id, session_data in self.active_sessions.items():
                last_activity_str = session_data['last_activity']
                last_activity = TimeManager.parse_utc_datetime(last_activity_str)
                
                if last_activity and (current_time - last_activity).total_seconds() > refresh_token_expires:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.active_sessions[session_id]
            
            if expired_sessions:
                logger.info(f"🧹 만료된 세션 정리: {len(expired_sessions)}개")
            
        except Exception as e:
            logger.error(f"❌ 세션 정리 중 오류: {str(e)}")
    
    def _generate_session_id(self, user_id: str) -> str:
        """인증된 사용자를 위한 세션 ID 생성 (표준화된 시간 사용)"""
        current_timestamp = int(TimeManager.utc_now().timestamp())
        session_data = f"{user_id}:{current_timestamp}"
        return hashlib.md5(session_data.encode()).hexdigest()