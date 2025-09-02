"""
LLM Factory
LLM 프로바이더 Repository 생성 팩토리
"""

from typing import Dict, Any
from utils.logging_utils import get_logger
from .interfaces import BaseLLMRepository

logger = get_logger(__name__)


class LLMFactory:
    """LLM Repository 팩토리 - 확장 가능한 구조"""
    
    # 프로바이더 레지스트리 (동적으로 등록 가능)
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, repository_class: type):
        """
        새로운 LLM 프로바이더 등록
        
        Args:
            name: 프로바이더 이름
            repository_class: Repository 클래스
        """
        cls._providers[name] = repository_class
        logger.info(f"✅ LLM 프로바이더 '{name}' 등록 완료")
    
    @classmethod
    def create_repository(cls, provider: str, config: Dict[str, Any]) -> BaseLLMRepository:
        """
        LLM Repository 생성
        
        Args:
            provider: LLM 제공업체 ('anthropic', 'openai' 등)
            config: 설정 딕셔너리 (api_key 등)
            
        Returns:
            BaseLLMRepository 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 프로바이더인 경우
        """
        # 늦은 import로 순환 참조 방지
        if not cls._providers:
            cls._initialize_default_providers()
        
        if provider not in cls._providers:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider}. 지원 목록: {supported}")
        
        try:
            repository_class = cls._providers[provider]
            repository = repository_class(**config)
            logger.info(f"✅ {provider} LLM Repository 생성 완료")
            return repository
        except Exception as e:
            logger.error(f"❌ {provider} LLM Repository 생성 실패: {str(e)}")
            raise
    
    @classmethod
    def _initialize_default_providers(cls):
        """기본 프로바이더 초기화 (늦은 import)"""
        try:
            from features.llm.repositories import AnthropicRepository
            cls.register_provider("anthropic", AnthropicRepository)
        except ImportError as e:
            logger.error(f"AnthropicRepository import 실패: {str(e)}")
            raise
        
        # 향후 추가 가능
        # try:
        #     from features.llm.repositories import OpenAIRepository
        #     cls.register_provider("openai", OpenAIRepository)
        # except ImportError:
        #     pass