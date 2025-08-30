"""
토큰 처리 유틸리티
JWT 토큰과 Google OAuth 토큰 처리를 위한 순수 함수들
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests
from utils.time_utils import TimeManager
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class TokenHandler:
    """토큰 처리 클래스 - Google OAuth와 JWT 토큰 관리"""
    
    def __init__(self, google_client_id: str, jwt_secret: str):
        """
        토큰 핸들러 초기화
        
        Args:
            google_client_id: Google OAuth 클라이언트 ID
            jwt_secret: JWT 서명용 비밀키
        """
        self.google_client_id = google_client_id
        self.jwt_secret = jwt_secret
        self.access_token_expires = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # 1시간
        self.refresh_token_expires = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000))  # 30일
    
    def verify_google_token(self, id_token_str: str) -> Dict[str, Any]:
        """
        Google ID 토큰 검증 (서명/만료/클레임 검증 - google-auth 사용)
        """
        try:
            if not self.google_client_id:
                raise ValueError("GOOGLE_CLIENT_ID가 설정되지 않았습니다")

            req = grequests.Request()
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str, req, self.google_client_id
            )

            iss = idinfo.get("iss")
            if iss not in ["accounts.google.com", "https://accounts.google.com"]:
                raise ValueError("Invalid issuer")

            if not idinfo.get("email"):
                raise ValueError("토큰에 이메일이 없습니다")
            if not idinfo.get("sub"):
                raise ValueError("토큰에 사용자 ID(sub)가 없습니다")

            # 선택: 이메일 검증 강제
            if not idinfo.get("email_verified", False):
                raise ValueError("이메일이 검증되지 않았습니다")

            user_info = {
                "user_id": idinfo["sub"],
                "email": idinfo["email"],
                "name": idinfo.get("name", ""),
                "picture": idinfo.get("picture", ""),
                "email_verified": idinfo.get("email_verified", False),
            }

            logger.info(f"✅ Google ID 토큰 검증 성공: {user_info['email']}")
            return {"success": True, "user_info": user_info}

        except Exception as e:
            logger.error(f"❌ Google 토큰 검증 실패: {str(e)}")
            return {"success": False, "error": f"{str(e)}"}
    
    def generate_jwt_tokens(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        JWT 액세스 토큰과 리프레시 토큰 생성 (시간 표준화)
        """
        try:
            # 표준화된 UTC 시간 사용
            current_time = TimeManager.utc_now()
            safe_issued_time = TimeManager.safe_utc_time(-30)  # 30초 전
            
            logger.info(f"🕐 표준화된 토큰 생성 시간: current={current_time.isoformat()}, iat={safe_issued_time.isoformat()}")
            
            # 액세스 토큰 페이로드
            access_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'name': user_info['name'],
                'picture': user_info.get('picture', ''),
                'iat': safe_issued_time,
                'exp': current_time + timedelta(seconds=self.access_token_expires),
                'type': 'access'
            }
            
            # 리프레시 토큰 페이로드
            refresh_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'iat': safe_issued_time,
                'exp': current_time + timedelta(seconds=self.refresh_token_expires),
                'type': 'refresh'
            }
            
            # JWT 토큰 생성
            access_token = jwt.encode(access_payload, self.jwt_secret, algorithm='HS256')
            refresh_token = jwt.encode(refresh_payload, self.jwt_secret, algorithm='HS256')
            
            logger.info(f"🔑 표준화된 JWT 토큰 생성 완료: {user_info['email']}")
            
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

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """리프레시 토큰을 사용하여 새로운 액세스 토큰 발급"""
        verification_result = self.verify_jwt_token(refresh_token, 'refresh')
        
        if not verification_result['success']:
            return verification_result
        
        user_info = verification_result['user_info']
        
        # 새로운 액세스 토큰만 생성
        try:
            current_time = TimeManager.utc_now()
            safe_issued_time = TimeManager.safe_utc_time(-30)
            
            access_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'iat': safe_issued_time,
                'exp': current_time + timedelta(seconds=self.access_token_expires),
                'type': 'access'
            }
            access_token = jwt.encode(access_payload, self.jwt_secret, algorithm='HS256')
            
            return {
                'success': True,
                'access_token': access_token,
                'expires_in': self.access_token_expires,
                'user_info': user_info
            }
        except Exception as e:
            logger.error(f"❌ 액세스 토큰 갱신 중 오류: {str(e)}")
            return {'success': False, 'error': '토큰 갱신 실패'}

    def verify_jwt_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        JWT 토큰 검증 (로그 최적화)
        """
        try:
            # JWT 토큰 디코드 (iat 검증 비활성화)
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=['HS256'],
                options={
                    'verify_exp': True,    # 만료 시간은 검증
                    'verify_iat': False,   # 발급 시간 검증 비활성화
                    'leeway': timedelta(seconds=120)  # 만료 시간에 대한 허용 오차
                }
            )
            
            # 토큰 타입 확인
            if payload.get('type') != token_type:
                raise ValueError(f'잘못된 토큰 타입: {payload.get("type")} (expected: {token_type})')
            
            # 만료 시간만 수동 검증 (표준화된 시간 사용)
            current_time = TimeManager.utc_now()
            exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
            
            if current_time > exp_time + timedelta(seconds=120):  # 2분 여유
                raise ValueError('토큰이 만료되었습니다')
            
            # 성공 로그를 DEBUG 레벨로 변경 (스팸 방지)
            logger.debug(f"✅ JWT 검증 성공: {payload['email']}")
            
            # 사용자 정보 반환
            user_info = {
                'user_id': payload['user_id'],
                'email': payload['email'],
                'name': payload.get('name', ''),
                'picture': payload.get('picture', ''),
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
            logger.error(f"❌ JWT 토큰 검증 실패: {str(e)}")
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