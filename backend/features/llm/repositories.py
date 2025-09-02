"""
LLM Repositories
LLM 프로바이더별 데이터 접근 계층
"""

import anthropic
from typing import Dict, Any, Optional, List
from core.llm.interfaces import BaseLLMRepository, LLMRequest, LLMResponse
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class AnthropicRepository(BaseLLMRepository):
    """Anthropic Claude API Repository"""
    
    def __init__(self, api_key: str, default_model: str = "claude-3-5-sonnet-20241022"):
        """
        Anthropic Repository 초기화
        
        Args:
            api_key: Anthropic API 키
            default_model: 기본 모델명
        """
        self.api_key = api_key
        self.default_model = default_model
        
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("✅ Anthropic Repository 초기화 완료")
        except Exception as e:
            logger.error(f"❌ Anthropic Repository 초기화 실패: {str(e)}")
            raise
    
    def execute_prompt(self, request: LLMRequest) -> LLMResponse:
        """
        프롬프트 실행
        
        Args:
            request: LLM 요청 객체
            
        Returns:
            LLMResponse: LLM 응답 객체
        """
        try:
            # Anthropic API 호출
            kwargs = {
                "model": request.model or self.default_model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": request.messages
            }
            
            # system 메시지가 있으면 추가
            if request.system:
                kwargs["system"] = request.system
            
            response = self.client.messages.create(**kwargs)
            
            # 응답 내용 추출
            content = response.content[0].text if response.content else ""
            
            # Usage 정보 추출 (있는 경우)
            usage = None
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, 'input_tokens', 0),
                    "output_tokens": getattr(response.usage, 'output_tokens', 0)
                }
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=response.model if hasattr(response, 'model') else request.model,
                finish_reason=getattr(response, 'stop_reason', None)
            )
            
        except Exception as e:
            logger.error(f"❌ Anthropic API 호출 실패: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """
        서비스 가용성 확인
        간단한 API 호출로 서비스 상태 확인
        """
        try:
            test_request = LLMRequest(
                model=self.default_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            response = self.execute_prompt(test_request)
            return bool(response.content)
        except Exception as e:
            logger.warning(f"Anthropic 서비스 가용성 확인 실패: {str(e)}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보 조회
        """
        return {
            "provider": "anthropic",
            "default_model": self.default_model,
            "available_models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307"
            ],
            "max_tokens": 4096,
            "supports_system_message": True,
            "supports_streaming": True
        }