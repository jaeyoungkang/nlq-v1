"""
Simple BigQuery Assistant - 유틸리티 패키지 (프롬프트 중앙 관리 적용)
LLM 클라이언트 통합 및 코드 구조 개선, 시간 처리 표준화, 프롬프트 중앙 관리 추가
"""

# 통합된 LLM 클라이언트 임포트 (프롬프트 중앙 관리 적용)
from .llm_client import LLMClientFactory, BaseLLMClient, AnthropicLLMClient
from .bigquery_utils import BigQueryClient
# 시간 처리 표준화 유틸리티
from .time_utils import TimeManager
# 인증 관련 (time_utils 의존성 때문에 나중에 임포트)
from .auth_utils import auth_manager, require_auth, optional_auth, check_usage_limit, admin_required
# 프롬프트 중앙 관리 시스템 임포트
from .prompts import prompt_manager

__all__ = [
    # LLM 관련 (프롬프트 중앙 관리 지원)
    'LLMClientFactory',
    'BaseLLMClient', 
    'AnthropicLLMClient',
    # BigQuery 관련
    'BigQueryClient',
    # 시간 처리 관련
    'TimeManager',
    # 인증 관련
    'auth_manager',
    'require_auth',
    'optional_auth', 
    'check_usage_limit',
    'admin_required',
    # 프롬프트 중앙 관리 관련
    'prompt_manager'
]

__version__ = '3.0.0-prompt-centralized'
__description__ = 'BigQuery AI Assistant 유틸리티 - 프롬프트 중앙 관리 시스템 적용'

# 패키지 정보
PACKAGE_INFO = {
    'name': 'BigQuery AI Assistant Utils',
    'version': __version__,
    'description': __description__,
    'components': {
        'llm_client': 'LLM 프로바이더 통합 인터페이스 (프롬프트 중앙 관리)',
        'bigquery_utils': 'Google BigQuery 연동 유틸리티',
        'time_utils': '시간 처리 표준화 유틸리티 (UTC 통일)',
        'auth_utils': '인증 및 사용량 관리 (시간 표준화 적용)',
        'prompts': '프롬프트 중앙 관리 시스템 (JSON 기반)'
    },
    'supported_llm_providers': ['anthropic'],
    'supported_databases': ['bigquery'],
    'features': {
        'time_standardization': True,
        'google_auth_bypass': True,
        'jwt_time_fix': True,
        'usage_tracking': True,
        'prompt_centralization': True,
        'json_templates': True,
        'hot_reload': True,
        'fallback_prompts': True
    }
}