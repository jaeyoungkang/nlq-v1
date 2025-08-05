"""
인증 유틸리티 모듈 (완전 버전)
Google OAuth 토큰 검증, JWT 토큰 관리, 세션 관리, 사용량 제한을 담당
"""

import os
import jwt
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from functools import wraps
from flask import request, jsonify, g
from google.auth.transport import requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

class AuthManager:
    """인증 관리 클래스 - 통합 버전"""
    
    def __init__(self):
        """인증 관리자 초기화"""
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        self.access_token_expires = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # 1시간
        self.refresh_token_expires = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000))  # 30일
        
        # 임시 세션 저장소 (메모리 기반)
        self.active_sessions = {}  # {session_id: user_info}
        self.usage_counter = {}    # {session_hash: {'count': int, 'date': str}}
        
        if not self.google_client_id or not self.jwt_secret:
            logger.warning("⚠️ Google Client ID 또는 JWT Secret이 설정되지 않았습니다")
    
    def verify_google_token(self, id_token_str: str) -> Dict[str, Any]:
        """
        Google ID 토큰 검증
        
        Args:
            id_token_str: Google에서 받은 ID 토큰
            
        Returns:
            검증 결과 및 사용자 정보
        """
        try:
            # Google ID 토큰 검증
            id_info = id_token.verify_oauth2_token(
                id_token_str, 
                requests.Request(), 
                self.google_client_id
            )
            
            # 토큰 발급자 확인
            if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('잘못된 토큰 발급자')
            
            # 사용자 정보 추출
            user_info = {
                'user_id': id_info['sub'],
                'email': id_info['email'],
                'name': id_info.get('name', ''),
                'picture': id_info.get('picture', ''),
                'email_verified': id_info.get('email_verified', False)
            }
            
            logger.info(f"✅ Google 토큰 검증 성공: {user_info['email']}")
            
            return {
                'success': True,
                'user_info': user_info
            }
            
        except ValueError as e:
            logger.error(f"❌ Google 토큰 검증 실패: {str(e)}")
            return {
                'success': False,
                'error': f'토큰 검증 실패: {str(e)}'
            }
        except Exception as e:
            logger.error(f"❌ Google 토큰 검증 중 오류: {str(e)}")
            return {
                'success': False,
                'error': f'인증 처리 중 오류: {str(e)}'
            }
    
    def generate_jwt_tokens(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        JWT 액세스 토큰과 리프레시 토큰 생성
        
        Args:
            user_info: 사용자 정보
            
        Returns:
            토큰 생성 결과
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # 액세스 토큰 페이로드
            access_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'name': user_info['name'],
                'iat': current_time,
                'exp': current_time + timedelta(seconds=self.access_token_expires),
                'type': 'access'
            }
            
            # 리프레시 토큰 페이로드
            refresh_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'iat': current_time,
                'exp': current_time + timedelta(seconds=self.refresh_token_expires),
                'type': 'refresh'
            }
            
            # JWT 토큰 생성
            access_token = jwt.encode(access_payload, self.jwt_secret, algorithm='HS256')
            refresh_token = jwt.encode(refresh_payload, self.jwt_secret, algorithm='HS256')
            
            # 세션 저장
            session_id = self._generate_session_id(user_info['user_id'])
            self.active_sessions[session_id] = {
                'user_info': user_info,
                'created_at': current_time.isoformat(),
                'last_activity': current_time.isoformat()
            }
            
            logger.info(f"🔑 JWT 토큰 생성 완료: {user_info['email']}")
            
            return {
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': self.access_token_expires,
                'user_info': user_info
            }
            
        except Exception as e:
            logger.error(f"❌ JWT 토큰 생성 중 오류: {str(e)}")
            return {
                'success': False,
                'error': f'토큰 생성 실패: {str(e)}'
            }
    
    def verify_jwt_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        JWT 토큰 검증
        
        Args:
            token: 검증할 JWT 토큰
            token_type: 토큰 타입 ('access' 또는 'refresh')
            
        Returns:
            검증 결과 및 사용자 정보
        """
        try:
            # JWT 토큰 디코드
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            # 토큰 타입 확인
            if payload.get('type') != token_type:
                raise ValueError(f'잘못된 토큰 타입: {payload.get("type")} (expected: {token_type})')
            
            # 만료 시간 확인
            exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
            if datetime.now(timezone.utc) > exp_time:
                raise ValueError('토큰이 만료되었습니다')
            
            # 사용자 정보 반환
            user_info = {
                'user_id': payload['user_id'],
                'email': payload['email'],
                'name': payload.get('name', ''),
                'is_authenticated': True
            }
            
            return {
                'success': True,
                'user_info': user_info,
                'payload': payload
            }
            
        except jwt.ExpiredSignatureError:
            return {
                'success': False,
                'error': '토큰이 만료되었습니다',
                'error_type': 'token_expired'
            }
        except jwt.InvalidTokenError as e:
            return {
                'success': False,
                'error': f'유효하지 않은 토큰: {str(e)}',
                'error_type': 'invalid_token'
            }
        except Exception as e:
            logger.error(f"❌ JWT 토큰 검증 중 오류: {str(e)}")
            return {
                'success': False,
                'error': f'토큰 검증 실패: {str(e)}',
                'error_type': 'verification_error'
            }
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        리프레시 토큰을 사용하여 새로운 액세스 토큰 생성
        
        Args:
            refresh_token: 리프레시 토큰
            
        Returns:
            새로운 액세스 토큰
        """
        try:
            # 리프레시 토큰 검증
            verification_result = self.verify_jwt_token(refresh_token, 'refresh')
            
            if not verification_result['success']:
                return verification_result
            
            user_info = verification_result['user_info']
            
            # 새로운 액세스 토큰 생성
            current_time = datetime.now(timezone.utc)
            access_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'name': user_info['name'],
                'iat': current_time,
                'exp': current_time + timedelta(seconds=self.access_token_expires),
                'type': 'access'
            }
            
            new_access_token = jwt.encode(access_payload, self.jwt_secret, algorithm='HS256')
            
            logger.info(f"🔄 액세스 토큰 갱신 완료: {user_info['email']}")
            
            return {
                'success': True,
                'access_token': new_access_token,
                'expires_in': self.access_token_expires,
                'user_info': user_info
            }
            
        except Exception as e:
            logger.error(f"❌ 토큰 갱신 중 오류: {str(e)}")
            return {
                'success': False,
                'error': f'토큰 갱신 실패: {str(e)}'
            }
    
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
        비인증 사용자를 위한 세션 ID 생성 (IP + User-Agent 기반)
        
        Args:
            ip_address: 클라이언트 IP 주소
            user_agent: 브라우저 User-Agent
            
        Returns:
            세션 ID
        """
        # IP와 User-Agent를 조합하여 해시 생성
        session_data = f"{ip_address}:{user_agent[:500]}:{datetime.now().strftime('%Y-%m-%d')}"
        session_hash = hashlib.md5(session_data.encode()).hexdigest()
        return f"guest_{session_hash[:16]}"
    
    def check_usage_limit(self, session_id: str) -> Tuple[bool, int]:
        """
        비인증 사용자의 사용량 제한 확인 (메모리 기반)
        
        Args:
            session_id: 세션 ID
            
        Returns:
            (사용 가능 여부, 남은 횟수)
        """
        today = datetime.now().strftime('%Y-%m-%d')
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
        비인증 사용자의 사용량 증가 (메모리 기반)
        
        Args:
            session_id: 세션 ID
            
        Returns:
            업데이트된 사용 횟수
        """
        today = datetime.now().strftime('%Y-%m-%d')
        session_key = f"{session_id}:{today}"
        
        if session_key not in self.usage_counter:
            self.usage_counter[session_key] = {'count': 0, 'date': today}
        
        self.usage_counter[session_key]['count'] += 1
        return self.usage_counter[session_key]['count']
    
    def check_usage_limit_with_bigquery(self, session_id: str, bigquery_client=None) -> Tuple[bool, int, Dict[str, Any]]:
        """
        BigQuery와 연동하여 사용량 제한 확인 (향상된 버전)
        
        Args:
            session_id: 세션 ID
            bigquery_client: BigQuery 클라이언트 (선택사항)
            
        Returns:
            (사용 가능 여부, 남은 횟수, 상세 정보)
        """
        # 메모리 기반 기본 확인
        can_use_memory, remaining_memory = self.check_usage_limit(session_id)
        
        # BigQuery 클라이언트가 있으면 정확한 사용량 확인
        if bigquery_client:
            try:
                # session_id에서 IP 추출 (guest_해시값 형태)
                ip_address = session_id.split('_')[-1] if '_' in session_id else 'unknown'
                usage_result = bigquery_client.get_usage_count(session_id, ip_address)
                
                if usage_result['success'] and not usage_result.get('table_missing', False):
                    daily_limit = usage_result.get('daily_limit', 10)
                    daily_count = usage_result.get('daily_count', 0)
                    remaining_bq = max(0, daily_limit - daily_count)
                    can_use_bq = daily_count < daily_limit
                    
                    return can_use_bq, remaining_bq, {
                        "source": "bigquery",
                        "daily_count": daily_count,
                        "daily_limit": daily_limit,
                        "last_request": usage_result.get('last_request')
                    }
                else:
                    logger.warning(f"BigQuery 사용량 조회 실패, 메모리 기반으로 폴백: {usage_result.get('error', 'table_missing')}")
                    
            except Exception as e:
                logger.warning(f"BigQuery 사용량 확인 중 오류, 메모리 기반으로 폴백: {str(e)}")
        
        # BigQuery 실패 시 메모리 기반 폴백
        return can_use_memory, remaining_memory, {
            "source": "memory",
            "daily_count": 10 - remaining_memory,
            "daily_limit": 10
        }
    
    def increment_usage_with_bigquery(self, session_id: str, ip_address: str, user_agent: str = "", bigquery_client=None) -> Dict[str, Any]:
        """
        BigQuery와 연동하여 사용량 증가 (향상된 버전)
        
        Args:
            session_id: 세션 ID
            ip_address: IP 주소
            user_agent: 브라우저 정보
            bigquery_client: BigQuery 클라이언트 (선택사항)
            
        Returns:
            업데이트 결과
        """
        # 메모리 기반 증가
        memory_count = self.increment_usage_count(session_id)
        
        # BigQuery 업데이트 시도
        if bigquery_client:
            try:
                bq_result = bigquery_client.update_usage_count(session_id, ip_address, user_agent)
                
                if bq_result['success'] and not bq_result.get('table_missing', False):
                    return {
                        "success": True,
                        "source": "bigquery",
                        "updated_count": memory_count,
                        "synchronized": True
                    }
                else:
                    logger.warning(f"BigQuery 사용량 업데이트 실패: {bq_result.get('error', 'table_missing')}")
                    
            except Exception as e:
                logger.warning(f"BigQuery 사용량 업데이트 중 오류: {str(e)}")
        
        # BigQuery 실패 시 메모리만 사용
        return {
            "success": True,
            "source": "memory",
            "updated_count": memory_count,
            "synchronized": False
        }
    
    def cleanup_expired_sessions(self):
        """만료된 세션 정리 (주기적 실행 권장)"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_sessions = []
            
            for session_id, session_data in self.active_sessions.items():
                last_activity = datetime.fromisoformat(session_data['last_activity'])
                # timezone이 없는 경우 UTC로 가정
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                
                if (current_time - last_activity).total_seconds() > self.refresh_token_expires:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.active_sessions[session_id]
            
            if expired_sessions:
                logger.info(f"🧹 만료된 세션 정리: {len(expired_sessions)}개")
            
            # 메모리 기반 사용량 카운터도 정리 (3일 이상 된 항목)
            expired_usage = []
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            for session_key in self.usage_counter.keys():
                if ':' in session_key:
                    _, date_str = session_key.rsplit(':', 1)
                    try:
                        usage_date = datetime.strptime(date_str, '%Y-%m-%d')
                        if (datetime.now() - usage_date).days > 3:
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
    
    def get_session_stats(self) -> Dict[str, Any]:
        """현재 세션 통계 조회"""
        try:
            current_time = datetime.now(timezone.utc)
            active_count = 0
            recent_count = 0
            
            # 활성/최근 세션 카운트
            for session_data in self.active_sessions.values():
                last_activity = datetime.fromisoformat(session_data['last_activity'])
                # timezone이 없는 경우 UTC로 가정
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                
                time_diff = (current_time - last_activity).total_seconds()
                
                if time_diff <= 3600:  # 1시간 이내
                    recent_count += 1
                if time_diff <= 86400:  # 24시간 이내
                    active_count += 1
            
            # 오늘의 사용량 카운터
            today = datetime.now().strftime('%Y-%m-%d')
            today_sessions = sum(1 for key in self.usage_counter.keys() if key.endswith(f':{today}'))
            
            return {
                'total_sessions': len(self.active_sessions),
                'active_sessions_24h': active_count,
                'recent_sessions_1h': recent_count,
                'guest_sessions_today': today_sessions,
                'total_usage_counters': len(self.usage_counter)
            }
            
        except Exception as e:
            logger.error(f"❌ 세션 통계 조회 중 오류: {str(e)}")
            return {'error': str(e)}
    
    def _generate_session_id(self, user_id: str) -> str:
        """인증된 사용자를 위한 세션 ID 생성"""
        timestamp = str(int(time.time()))
        session_data = f"{user_id}:{timestamp}"
        return hashlib.md5(session_data.encode()).hexdigest()


# 전역 인증 관리자 인스턴스
auth_manager = AuthManager()


# === 데코레이터 함수들 ===

def require_auth(f):
    """
    인증이 필수인 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': '인증 토큰이 필요합니다',
                'error_type': 'missing_token'
            }), 401
        
        token = auth_header.split(' ')[1]
        verification_result = auth_manager.verify_jwt_token(token)
        
        if not verification_result['success']:
            return jsonify({
                'success': False,
                'error': verification_result['error'],
                'error_type': verification_result.get('error_type', 'auth_error')
            }), 401
        
        # 요청 컨텍스트에 사용자 정보 저장
        g.current_user = verification_result['user_info']
        g.is_authenticated = True
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_auth(f):
    """
    선택적 인증을 위한 데코레이터 (인증된 사용자와 비인증 사용자 모두 허용)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        # 인증 토큰이 있는 경우 검증
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            verification_result = auth_manager.verify_jwt_token(token)
            
            if verification_result['success']:
                g.current_user = verification_result['user_info']
                g.is_authenticated = True
            else:
                # 토큰이 유효하지 않은 경우 비인증 사용자로 처리
                g.current_user = None
                g.is_authenticated = False
        else:
            # 토큰이 없는 경우 비인증 사용자로 처리
            g.current_user = None
            g.is_authenticated = False
        
        return f(*args, **kwargs)
    
    return decorated_function


def check_usage_limit(f):
    """
    비인증 사용자의 사용량 제한을 확인하는 데코레이터 (BigQuery 통합)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 인증된 사용자는 제한 없음
        if getattr(g, 'is_authenticated', False):
            return f(*args, **kwargs)
        
        # 비인증 사용자의 경우 사용량 확인
        ip_address = request.remote_addr or 'unknown'
        user_agent = request.headers.get('User-Agent', '')
        session_id = auth_manager.generate_session_id(ip_address, user_agent)
        
        # BigQuery 클라이언트 가져오기 (app.py에서 전역 변수로 설정된 것 사용)
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        # 향상된 사용량 확인
        can_use, remaining, usage_info = auth_manager.check_usage_limit_with_bigquery(
            session_id, bigquery_client
        )
        
        if not can_use:
            return jsonify({
                'success': False,
                'error': '일일 사용 제한에 도달했습니다. 로그인하여 무제한으로 이용하세요.',
                'error_type': 'usage_limit_exceeded',
                'usage': {
                    'daily_limit': usage_info.get('daily_limit', 10),
                    'daily_count': usage_info.get('daily_count', 10),
                    'remaining': 0,
                    'source': usage_info.get('source', 'unknown')
                }
            }), 429  # Too Many Requests
        
        # 사용량 증가
        increment_result = auth_manager.increment_usage_with_bigquery(
            session_id, ip_address, user_agent, bigquery_client
        )
        
        # 요청 컨텍스트에 세션 정보 저장
        g.session_id = session_id
        g.remaining_usage = remaining - 1
        g.usage_source = increment_result.get('source', 'memory')
        g.usage_synchronized = increment_result.get('synchronized', False)
        
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """
    관리자 권한이 필요한 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 먼저 인증 확인
        if not getattr(g, 'is_authenticated', False):
            return jsonify({
                'success': False,
                'error': '인증이 필요합니다',
                'error_type': 'authentication_required'
            }), 401
        
        # 관리자 권한 확인 (환경변수로 관리자 이메일 도메인 설정)
        user_email = g.current_user.get('email', '')
        admin_domains = os.getenv('ADMIN_EMAIL_DOMAINS', '').split(',')
        admin_emails = os.getenv('ADMIN_EMAILS', '').split(',')
        
        is_admin = False
        
        # 도메인 기반 확인
        if admin_domains and admin_domains[0]:  # 빈 문자열이 아닌 경우
            is_admin = any(user_email.endswith(domain.strip()) for domain in admin_domains if domain.strip())
        
        # 특정 이메일 기반 확인
        if not is_admin and admin_emails and admin_emails[0]:  # 빈 문자열이 아닌 경우
            is_admin = user_email in [email.strip() for email in admin_emails if email.strip()]
        
        # 환경변수가 설정되지 않은 경우 모든 인증된 사용자를 관리자로 처리 (개발용)
        if not admin_domains[0] and not admin_emails[0]:
            logger.warning("⚠️ 관리자 설정이 없습니다. 모든 인증된 사용자를 관리자로 처리합니다.")
            is_admin = True
        
        if not is_admin:
            return jsonify({
                'success': False,
                'error': '관리자 권한이 필요합니다',
                'error_type': 'insufficient_permissions'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function