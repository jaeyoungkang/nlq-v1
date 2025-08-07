"""
인증 유틸리티 모듈 - 하위 호환성을 위한 래퍼
기존 코드와의 호환성을 유지하면서 새로운 모듈 구조로 리다이렉트 - 로그인 필수 버전
"""

import logging
from .auth import auth_manager, require_auth, admin_required

logger = logging.getLogger(__name__)

# 기존 코드와의 호환성을 위해 exports 정리
__all__ = [
    'auth_manager',
    'require_auth', 
    'admin_required'
]

logger.info("✅ 인증 시스템 모듈 정리 완료 - 로그인 필수 버전")