"""
Context 관련 공통 모델

ContextBlock: 완전한 대화 컨텍스트 단위
- 사용자 요청 + AI 응답 + 실행 결과가 하나의 블록으로 맥락 보존
- 용도별 유틸리티 함수 제공 (토큰 절약용 vs 맥락 보존용)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class BlockType(Enum):
    """컨텍스트 블록 타입"""
    QUERY = "QUERY"               # SQL 쿼리 실행
    ANALYSIS = "ANALYSIS"         # 데이터 분석
    METADATA = "METADATA"         # 스키마 정보 조회


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
    
    # 생성된 쿼리 (별도 필드)
    generated_query: Optional[str] = None
    
    # 실행 결과
    execution_result: Optional[Dict[str, Any]] = None  # {"data": [...], "row_count": N}
    
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
            'generated_query': self.generated_query,
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
        """LLM 통신용 AI 응답 포맷으로 변환 (맥락 보존용 - 메타정보 포함)"""
        return {
            "role": "assistant",
            "content": self.assistant_response,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            # 맥락 보존을 위한 실행 결과 메타정보 포함
            "query_row_count": (self.execution_result or {}).get("row_count", 0),
            "metadata": {
                "block_id": self.block_id,
                "generated_query": self.generated_query,
                "block_type": self.block_type.value if isinstance(self.block_type, Enum) else self.block_type
            }
        }
    


# 유틸리티 함수들
def context_blocks_to_llm_format(blocks: List[ContextBlock]) -> List[Dict[str, Any]]:
    """ContextBlock 리스트를 LLM 통신용 포맷으로 변환 (대화 히스토리용 - 토큰 절약)"""
    llm_context = []
    for block in blocks:
        # 사용자 요청 추가
        llm_context.append(block.to_llm_format())
        # AI 응답 추가 (빈 상태라도 구조 유지)
        llm_context.append(block.to_assistant_llm_format())
    return llm_context


def context_blocks_to_complete_format(blocks: List[ContextBlock]) -> List[Dict[str, Any]]:
    """ContextBlock 리스트를 완전한 형태로 딕셔너리 변환 (맥락 보존용)"""
    return [block.to_dict() for block in blocks]

def create_analysis_context(blocks: List[ContextBlock]) -> Dict[str, Any]:
    """ContextBlock 설계 의도에 따른 분석용 컨텍스트 생성 - 맥락 보존"""
    # 전체 데이터 행 수 계산 (통계용)
    total_row_count = sum(
        len((block.execution_result or {}).get("data", [])) 
        for block in blocks
    )
    
    return {
        "context_blocks": blocks,  # 완전한 ContextBlock 단위 - 맥락 보존
        "meta": {
            "total_row_count": total_row_count,
            "blocks_count": len(blocks)
        },
        "limits": {"max_rows": 100}
    }
