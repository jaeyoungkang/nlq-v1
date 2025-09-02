"""
LLM Provider Interfaces
LLM 프로바이더가 구현해야 하는 인터페이스 정의
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class LLMRequest:
    """LLM 요청 데이터 모델"""
    model: str
    messages: List[Dict[str, str]]
    max_tokens: int = 4000
    temperature: float = 0.7
    system: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM 응답 데이터 모델"""
    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class BaseLLMRepository(ABC):
    """
    LLM Repository 인터페이스
    모든 LLM 프로바이더 구현체가 준수해야 하는 기본 인터페이스
    """
    
    @abstractmethod
    def __init__(self, api_key: str, **kwargs):
        """
        Repository 초기화
        
        Args:
            api_key: API 인증 키
            **kwargs: 프로바이더별 추가 설정
        """
        pass
    
    @abstractmethod
    def execute_prompt(self, request: LLMRequest) -> LLMResponse:
        """
        프롬프트 실행
        
        Args:
            request: LLM 요청 객체
            
        Returns:
            LLMResponse: LLM 응답 객체
            
        Raises:
            Exception: API 호출 실패 시
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        서비스 가용성 확인
        
        Returns:
            bool: 서비스 사용 가능 여부
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보 조회
        
        Returns:
            Dict: 현재 설정된 모델 정보
        """
        pass