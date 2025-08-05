"""
Simple BigQuery Assistant - 유틸리티 패키지 (리팩토링 버전)
LLM 클라이언트 통합 및 코드 구조 개선
"""

# 통합된 LLM 클라이언트 임포트
from .llm_client import LLMClientFactory, BaseLLMClient, AnthropicLLMClient
from .bigquery_utils import BigQueryClient

__all__ = [
    # LLM 관련
    'LLMClientFactory',
    'BaseLLMClient', 
    'AnthropicLLMClient',
    # BigQuery 관련
    'BigQueryClient'
]

__version__ = '2.1.0-refactored'
__description__ = 'BigQuery AI Assistant 유틸리티 - 통합 LLM 클라이언트 및 BigQuery 연동'

# 패키지 정보
PACKAGE_INFO = {
    'name': 'BigQuery AI Assistant Utils',
    'version': __version__,
    'description': __description__,
    'components': {
        'llm_client': 'LLM 프로바이더 통합 인터페이스',
        'bigquery_utils': 'Google BigQuery 연동 유틸리티'
    },
    'supported_llm_providers': ['anthropic'],
    'supported_databases': ['bigquery']
}