"""
Query Processing Feature 데이터 모델
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from core.models import ContextBlock, BlockType
import uuid
    


@dataclass
class QueryRequest:
    """쿼리 요청 - ContextBlock 기반"""
    user_id: str
    query: str
    context_block: Optional[ContextBlock] = None
    
    def __post_init__(self):
        """초기화 후 처리: ContextBlock 자동 생성 - 단순화"""
        if not self.context_block:
            # 새로운 ContextBlock 생성
            self.context_block = ContextBlock(
                block_id=str(uuid.uuid4()),
                user_id=self.user_id,
                timestamp=datetime.now(timezone.utc),
                block_type=BlockType.QUERY,
                user_request=self.query,  # 단순 문자열
                assistant_response="",  # 빈 문자열
                status="pending"
            )


@dataclass  
class QueryResult:
    """쿼리 결과 - ContextBlock 포함"""
    success: bool
    result_type: str  # "query_result", "analysis_result", "out_of_scope_result"
    context_block: Optional[ContextBlock] = None  # 처리된 ContextBlock
    data: Optional[List[Dict[str, Any]]] = None
    generated_query: Optional[str] = None
    row_count: int = 0
    content: Optional[str] = None  # 분석이나 기타 응답
    error: Optional[str] = None

