"""
Context 관련 공통 모델
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class BlockType(Enum):
    """컨텍스트 블록 타입"""
    QUERY = "QUERY"               # SQL 쿼리 실행
    ANALYSIS = "ANALYSIS"         # 데이터 분석
    METADATA = "METADATA"         # 메타데이터 조회


@dataclass
class ContextBlock:
    """컨텍스트 블록: 하나의 완전한 대화 컨텍스트 단위"""
    # 기본 식별자
    block_id: str
    user_id: str
    timestamp: datetime
    block_type: BlockType
    
    # 사용자 요청
    user_request: str  # 단순 문자열
    
    # AI 응답
    assistant_response: str = ""  # 단순 문자열
    
    # 실행 결과
    execution_result: Optional[Dict[str, Any]] = None  # {"data": [...], "row_count": N, "execution_time_ms": 123}
    
    # 상태 관리
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'block_id': self.block_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'block_type': self.block_type.value if isinstance(self.block_type, Enum) else self.block_type,
            'user_request': self.user_request,
            'assistant_response': self.assistant_response,
            'execution_result': self.execution_result,
            'status': self.status
        }
    
    def to_llm_format(self) -> Dict[str, Any]:
        """LLM 통신용 사용자 요청 포맷으로 변환"""
        return {
            "role": "user",
            "content": self.user_request,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "metadata": {
                "block_id": self.block_id,
                "block_type": self.block_type.value if isinstance(self.block_type, Enum) else self.block_type
            }
        }
    
    def to_assistant_llm_format(self) -> Dict[str, Any]:
        """LLM 통신용 AI 응답 포맷으로 변환"""
        return {
            "role": "assistant",
            "content": self.assistant_response,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "query_result_data": self.execution_result.get("data") if self.execution_result else None,
            "query_row_count": self.execution_result.get("row_count") if self.execution_result else 0,
            "metadata": {
                "block_id": self.block_id,
                "generated_sql": self.execution_result.get("generated_sql") if self.execution_result else None
            }
        }


# 유틸리티 함수
def context_blocks_to_llm_format(blocks: List[ContextBlock]) -> List[Dict[str, Any]]:
    """ContextBlock 리스트를 LLM 통신용 포맷으로 변환"""
    llm_context = []
    for block in blocks:
        # 사용자 요청 추가
        llm_context.append(block.to_llm_format())
        # AI 응답이 있으면 추가
        if block.assistant_response:
            llm_context.append(block.to_assistant_llm_format())
    return llm_context