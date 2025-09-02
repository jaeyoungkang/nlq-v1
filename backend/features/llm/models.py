"""
LLM Feature Models
LLM 관련 요청/응답 데이터 모델
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
from core.models.context import ContextBlock


class LLMCategory(Enum):
    """LLM 처리 카테고리"""
    CLASSIFICATION = "classification"
    SQL_GENERATION = "sql_generation"
    DATA_ANALYSIS = "data_analysis"
    GUIDE = "guide"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class ClassificationRequest:
    """입력 분류 요청"""
    user_input: str
    context_blocks: Optional[List[ContextBlock]] = None


@dataclass
class ClassificationResponse:
    """입력 분류 응답"""
    category: str
    confidence: float
    reasoning: Optional[str] = None


@dataclass
class SQLGenerationRequest:
    """SQL 생성 요청"""
    user_question: str
    project_id: str
    default_table: str
    context_blocks: Optional[List[ContextBlock]] = None
    schema_info: Optional[Dict[str, Any]] = None


@dataclass
class SQLGenerationResponse:
    """SQL 생성 응답"""
    sql_query: str
    explanation: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class AnalysisRequest:
    """데이터 분석 요청"""
    user_question: str
    context_blocks: List[ContextBlock]
    additional_context: Optional[str] = None


@dataclass
class AnalysisResponse:
    """데이터 분석 응답"""
    analysis: str
    insights: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None


@dataclass
class GuideRequest:
    """가이드 요청"""
    question: str
    context: Optional[str] = None


@dataclass
class OutOfScopeRequest:
    """범위 외 요청"""
    question: str
    detected_intent: Optional[str] = None