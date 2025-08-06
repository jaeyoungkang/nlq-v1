"""
인증 관리자 핵심 클래스
사용자 세션 관리, 사용량 추적, 세션 정리 등 핵심 기능
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from .token_handler import TokenHandler
from ..time_utils import TimeManager

logger = logging.getLogger(__name__)

class AuthManager:
    """인증 관리 클래스 - 핵심 기능만 담당"""
    
    def __init__(self):
        """인증 관리자 초기화"""
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        
        # 토큰 처리기 초기화
        self.token_handler = TokenHandler(
            google_client_id=self.google_client_id,
            jwt_secret=self.jwt_secret
        )
        
        # 임시 세션 저장소 (메모리 기반)
        self.active_sessions = {}  # {session_id: user_info}
        self.usage_counter = {}    # {session_hash: {'count': int, 'date': str}}
        
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
    
    def generate_session_id(self, ip_address: str, user_agent: str) -> str:
        """
        비인증 사용자를 위한 세션 ID 생성 (표준화된 시간 사용)
        """
        # 표준화된 UTC 날짜 사용
        utc_date = TimeManager.utc_date_string()
        session_data = f"{ip_address}:{user_agent[:500]}:{utc_date}"
        session_hash = hashlib.md5(session_data.encode()).hexdigest()
        return f"guest_{session_hash[:16]}"
    
    def check_usage_limit(self, session_id: str) -> Tuple[bool, int]:
        """
        비인증 사용자의 사용량 제한 확인 (표준화된 시간 사용)
        """
        # 표준화된 UTC 날짜 사용
        today = TimeManager.utc_date_string()
        session_key = f"{session_id}:{today}"
        
        # 현재 사용량 확인
        current_usage = self.usage_counter.get(session_key, {'count': 0, 'date': today})
        
        # 날짜가 다르면 카운터 리셋
        if current_usage['date'] != today:
            current_usage = {'count': 0, 'date': today}
            self.usage_counter[session_key] = current_usage
        
        daily_limit = int(os.getenv('DAILY_USAGE_LIMIT', '10'))
        remaining = max(0, daily_limit - current_usage['count'])
        can_use = current_usage['count'] < daily_limit
        
        return can_use, remaining
    
    def increment_usage_count(self, session_id: str) -> int:
        """
        비인증 사용자의 사용량 증가 (표준화된 시간 사용)
        """
        # 표준화된 UTC 날짜 사용
        today = TimeManager.utc_date_string()
        session_key = f"{session_id}:{today}"
        
        if session_key not in self.usage_counter:
            self.usage_counter[session_key] = {'count': 0, 'date': today}
        
        self.usage_counter[session_key]['count'] += 1
        return self.usage_counter[session_key]['count']

    def check_usage_limit_with_bigquery(self, session_id: str, bigquery_client: Optional[Any] = None) -> Tuple[bool, int, Dict[str, Any]]:
        """
        BigQuery와 연동하여 사용량 제한 확인, 실패 시 메모리 기반으로 대체
        """
        from flask import request
        ip_address = request.remote_addr or 'unknown'
        daily_limit = int(os.getenv('DAILY_USAGE_LIMIT', '10'))
        
        if bigquery_client:
            try:
                usage_result = bigquery_client.get_usage_count(session_id, ip_address)
                if usage_result['success']:
                    daily_count = usage_result.get('daily_count', 0)
                    remaining = max(0, daily_limit - daily_count)
                    can_use = remaining > 0
                    usage_info = {
                        'daily_count': daily_count,
                        'remaining': remaining,
                        'daily_limit': daily_limit,
                        'source': 'bigquery',
                        'last_request': usage_result.get('last_request')
                    }
                    return can_use, remaining, usage_info
                else:
                    logger.warning(f"BigQuery 사용량 확인 실패: {usage_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"BigQuery 사용량 확인 실패: {e}")
        
        # BigQuery 실패 또는 클라이언트 없음 - 메모리 기반으로 대체
        can_use, remaining = self.check_usage_limit(session_id)
        usage_info = {
            'daily_count': daily_limit - remaining,
            'remaining': remaining,
            'daily_limit': daily_limit,
            'source': 'memory'
        }
        return can_use, remaining, usage_info

    def increment_usage_with_bigquery(self, session_id: str, ip_address: str, user_agent: str, bigquery_client: Optional[Any] = None) -> Dict[str, Any]:
        """
        BigQuery와 연동하여 사용량 증가, 실패 시 메모리 기반으로 대체
        """
        if bigquery_client:
            try:
                update_result = bigquery_client.update_usage_count(session_id, ip_address, user_agent)
                if update_result['success']:
                    # 메모리 카운터도 동기화
                    self.increment_usage_count(session_id)
                    return {
                        'success': True,
                        'source': 'bigquery',
                        'synchronized': True,
                        'updated_count': update_result.get('updated_count', 1)
                    }
                else:
                    logger.warning(f"BigQuery 사용량 업데이트 실패: {update_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"BigQuery 사용량 업데이트 실패: {e}")

        # BigQuery 실패 또는 클라이언트 없음 - 메모리 기반으로 대체
        count = self.increment_usage_count(session_id)
        return {
            'success': True,
            'source': 'memory',
            'synchronized': False,
            'updated_count': count
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
            
            # 메모리 기반 사용량 카운터도 정리 (3일 이상 된 항목)
            expired_usage = []
            current_date_str = TimeManager.utc_date_string()
            current_date = TimeManager.utc_now().date()
            
            for session_key in self.usage_counter.keys():
                if ':' in session_key:
                    _, date_str = session_key.rsplit(':', 1)
                    try:
                        usage_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if (current_date - usage_date).days > 3:
                            expired_usage.append(session_key)
                    except ValueError:
                        # 잘못된 형식의 키는 삭제
                        expired_usage.append(session_key)
            
            for session_key in expired_usage:
                del self.usage_counter[session_key]
            
            if expired_usage:
                logger.info(f"🧹 만료된 사용량 카운터 정리: {len(expired_usage)}개")
            
        except Exception as e:
            logger.error(f"❌ 세션 정리 중 오류: {str(e)}")
    
    def _generate_session_id(self, user_id: str) -> str:
        """인증된 사용자를 위한 세션 ID 생성 (표준화된 시간 사용)"""
        current_timestamp = int(TimeManager.utc_now().timestamp())
        session_data = f"{user_id}:{current_timestamp}"
        return hashlib.md5(session_data.encode()).hexdigest()