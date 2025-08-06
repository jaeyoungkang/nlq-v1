"""
프롬프트 중앙 관리 패키지
LLM 프롬프트를 JSON 파일로 분리하여 중앙에서 관리
"""

from .templates import PromptManager

# 전역 프롬프트 매니저 인스턴스
prompt_manager = PromptManager()

__all__ = [
    'PromptManager',
    'prompt_manager'
]

__version__ = '1.0.0'
__description__ = 'LLM 프롬프트 중앙 관리 시스템'

# 패키지 정보
PACKAGE_INFO = {
    'name': 'BigQuery AI Assistant Prompts',
    'version': __version__,
    'description': __description__,
    'features': {
        'json_templates': True,
        'variable_substitution': True,
        'caching': True,
        'hot_reload': True,
        'fallback_prompts': True
    }
}