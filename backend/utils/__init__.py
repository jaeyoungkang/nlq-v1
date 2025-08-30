"""
NLQ-v1 Backend - 유틸리티 패키지
Feature-driven 아키텍처 기반, Repository 패턴 적용
"""

# LLM 클라이언트
from .llm_client import LLMClientFactory, BaseLLMClient, AnthropicLLMClient
# 시간 처리 표준화 유틸리티
from .time_utils import TimeManager
# 인증 관련 데코레이터
from .decorators import require_auth, admin_required
# 토큰 관리 유틸리티
from .token_utils import TokenHandler
# 표준화된 로깅 유틸리티
from .logging_utils import get_logger
# 에러 처리 유틸리티
from .error_utils import ErrorResponse, SuccessResponse
# 프롬프트 중앙 관리 시스템
from .prompts import prompt_manager
# MetaSync 캐시 로더
from .metasync_cache_loader import MetaSyncCacheLoader, get_metasync_cache_loader

__all__ = [
    # LLM 관련
    'LLMClientFactory',
    'BaseLLMClient', 
    'AnthropicLLMClient',
    # 시간 처리
    'TimeManager',
    # 인증 관련
    'require_auth',
    'admin_required',
    'TokenHandler',
    # 로깅 및 에러 처리
    'get_logger',
    'ErrorResponse',
    'SuccessResponse',
    # 프롬프트 관리
    'prompt_manager',
    # MetaSync 캐시
    'MetaSyncCacheLoader',
    'get_metasync_cache_loader'
]

__version__ = '1.0.0-feature-driven'
__description__ = 'NLQ-v1 Backend 유틸리티 - Feature-driven 아키텍처'

# 패키지 정보
PACKAGE_INFO = {
    'name': 'NLQ-v1 Backend Utils',
    'version': __version__,
    'description': __description__,
    'architecture': 'feature-driven',
    'components': {
        'llm_client': 'LLM 프로바이더 통합 인터페이스 (Anthropic Claude)',
        'time_utils': '시간 처리 표준화 유틸리티 (UTC 통일)',
        'auth_decorators': '인증 데코레이터 (@require_auth)',
        'token_utils': 'JWT 토큰 관리 유틸리티',
        'logging_utils': '표준화된 로깅 시스템',
        'error_utils': '통합 에러 응답 시스템',
        'prompts': '프롬프트 중앙 관리 시스템 (JSON 기반)',
        'metasync_cache': 'MetaSync 캐시 시스템 연동'
    },
    'supported_llm_providers': ['anthropic'],
    'supported_databases': ['bigquery'],
    'features': {
        'feature_driven_architecture': True,
        'repository_pattern': True,
        'chat_service_orchestration': True,
        'jwt_authentication': True,
        'google_oauth': True,
        'standardized_logging': True,
        'unified_error_handling': True,
        'prompt_centralization': True,
        'metasync_integration': True,
        'bigquery_direct_access': True
    }
}