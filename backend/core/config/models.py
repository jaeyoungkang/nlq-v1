"""LLM 설정 데이터 모델

이 모듈은 LLM 서비스 설정을 위한 데이터 모델을 정의합니다.
각 태스크별로 다른 LLM 파라미터를 관리할 수 있도록 구조화되어 있습니다.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class LLMModelConfig:
    """개별 LLM 모델 설정
    
    Attributes:
        model_id: 사용할 LLM 모델 ID (예: claude-3-5-sonnet-20241022)
        max_tokens: 최대 생성 토큰 수
        temperature: 생성 다양성 (0.0-1.0)
        confidence: 응답 신뢰도 임계값 (0.0-1.0, 선택적)
    """
    model_id: str
    max_tokens: int
    temperature: float
    confidence: Optional[float] = None
    
    def __post_init__(self):
        """설정값 검증"""
        if not 0 <= self.temperature <= 1:
            raise ValueError(f"Temperature must be between 0 and 1, got {self.temperature}")
        if self.max_tokens <= 0:
            raise ValueError(f"Max tokens must be positive, got {self.max_tokens}")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result


@dataclass
class LLMTaskConfig:
    """태스크별 LLM 설정 모음
    
    각 태스크 유형에 대해 최적화된 LLM 설정을 관리합니다.
    
    Attributes:
        classification: 입력 분류용 설정
        sql_generation: SQL 쿼리 생성용 설정
        data_analysis: 데이터 분석용 설정
        guide_generation: 가이드 생성용 설정
        out_of_scope: 범위 외 응답용 설정
    """
    classification: LLMModelConfig
    sql_generation: LLMModelConfig
    data_analysis: LLMModelConfig
    guide_generation: LLMModelConfig
    out_of_scope: LLMModelConfig
    
    def get_config(self, task_type: str) -> LLMModelConfig:
        """태스크 유형별 설정 조회
        
        Args:
            task_type: 태스크 유형 (classification, sql_generation 등)
            
        Returns:
            해당 태스크의 LLM 설정
            
        Raises:
            ValueError: 알 수 없는 태스크 유형
        """
        task_configs = {
            "classification": self.classification,
            "sql_generation": self.sql_generation,
            "data_analysis": self.data_analysis,
            "guide_generation": self.guide_generation,
            "out_of_scope": self.out_of_scope
        }
        
        if task_type not in task_configs:
            raise ValueError(f"Unknown task type: {task_type}")
        
        return task_configs[task_type]


@dataclass
class LLMConfig:
    """전체 LLM 설정
    
    Attributes:
        default_model: 기본 모델 ID
        available_models: 사용 가능한 모델 목록
        tasks: 태스크별 설정
    """
    default_model: str
    available_models: list[str]
    tasks: LLMTaskConfig
    
    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인"""
        return model_id in self.available_models