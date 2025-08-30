"""
Data Analysis Feature 데이터 모델
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from core.models import ContextBlock


@dataclass
class AnalysisRequest:
    """데이터 분석 요청"""
    user_id: str
    query: str
    context_block: ContextBlock
    context_blocks: List[ContextBlock] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """데이터 분석 결과"""
    success: bool
    analysis_content: str
    context_block: Optional[ContextBlock] = None
    error: Optional[str] = None