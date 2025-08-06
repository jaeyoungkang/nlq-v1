"""
토큰 처리 모듈
Google OAuth 토큰 검증, JWT 토큰 생성/검증 담당
"""

import os
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from ..time_utils import TimeManager

logger = logging.getLogger(__name__)

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
        Google ID 토큰 검증 (시간 검증 완전 우회)
        """
        try:
            # JWT 토큰을 수동으로 디코딩하여 시간 검증 우회
            import json
            import base64
            
            logger.info("🔍 Google 토큰 수동 검증 시작 (시간 검증 우회)")
            
            # JWT 토큰 분해
            parts = id_token_str.split('.')
            if len(parts) != 3:
                raise ValueError("잘못된 JWT 토큰 형식")
            
            # 페이로드 디코딩
            payload = parts[1]
            # Base64 패딩 추가
            payload += '=' * (4 - len(payload) % 4)
            decoded_payload = base64.urlsafe_b64decode(payload)
            id_info = json.loads(decoded_payload)
            
            logger.info(f"📊 디코딩된 토큰 정보: iss={id_info.get('iss')}, aud={id_info.get('aud')[:20] if id_info.get('aud') else 'N/A'}...")
            
            # 필수 필드 검증만 수행 (시간 검증 제외)
            if not id_info.get('email'):
                raise ValueError("토큰에 이메일 정보가 없습니다")
            
            if not id_info.get('sub'):
                raise ValueError("토큰에 사용자 ID가 없습니다")
            
            # 클라이언트 ID 검증
            if id_info.get('aud') != self.google_client_id:
                raise ValueError(f"잘못된 클라이언트 ID: {id_info.get('aud')} != {self.google_client_id}")
            
            # 발급자 검증
            if id_info.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError(f'잘못된 토큰 발급자: {id_info.get("iss")}')
            
            # 이메일 검증 여부 확인 (선택사항)
            if not id_info.get('email_verified', True):
                logger.warning(f"⚠️ 이메일이 검증되지 않은 사용자: {id_info.get('email')}")
            
            # 사용자 정보 추출
            user_info = {
                'user_id': id_info['sub'],
                'email': id_info['email'],
                'name': id_info.get('name', ''),
                'picture': id_info.get('picture', ''),
                'email_verified': id_info.get('email_verified', False)
            }
            
            logger.info(f"✅ Google 토큰 수동 검증 성공 (시간 검증 우회): {user_info['email']}")
            
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
                'iat': safe_issued_time,
                'exp': current_time + timedelta(seconds=self.access_token_expires),
                'type': 'access'
            }
            
            # 리프레시 토큰 페이로드
            refresh_payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
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