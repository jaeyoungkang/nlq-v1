"""
인증 유틸리티 모듈 - 하위 호환성을 위한 래퍼
기존 코드와의 호환성을 유지하면서 새로운 모듈 구조로 리다이렉트
"""

import logging
from .auth import auth_manager, require_auth, optional_auth, check_usage_limit, admin_required

logger = logging.getLogger(__name__)

# 기존 코드와의 호환성을 위해 모든 exports를 그대로 유지
__all__ = [
    'auth_manager',
    'require_auth', 
    'optional_auth',
    'check_usage_limit',
    'admin_required'
]

logger.info("✅ 인증 시스템 모듈 분할 완료 - 하위 호환성 유지됨")