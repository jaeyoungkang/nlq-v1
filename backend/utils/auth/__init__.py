"""
인증 시스템 패키지 초기화
분할된 인증 모듈들을 통합하여 기존 인터페이스 유지 - 로그인 필수 버전
"""

from .auth_manager import AuthManager
from .decorators import require_auth, admin_required

# 전역 인증 매니저 인스턴스 생성
auth_manager = AuthManager()

__all__ = [
    'auth_manager',
    'require_auth', 
    'admin_required'
]