"""
Chat 모델 정의
대화 요청/응답 및 컨텍스트 관련 데이터 모델
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from core.models import ContextBlock


class ChatRequest(BaseModel):
    """대화 요청 모델"""
    user_id: str = Field(..., description="사용자 ID")
    message: str = Field(..., description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="세션 ID")
    context_limit: int = Field(5, description="컨텍스트 제한")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "message": "지난 달 매출은 얼마야?",
                "session_id": "session456",
                "context_limit": 5
            }
        }


class ChatResponse(BaseModel):
    """대화 응답 모델"""
    success: bool = Field(..., description="처리 성공 여부")
    message: str = Field(..., description="응답 메시지")
    category: str = Field(..., description="입력 카테고리")
    data: Optional[Dict[str, Any]] = Field(None, description="응답 데이터")
    generated_sql: Optional[str] = Field(None, description="생성된 쿼리 (API 호환성)")
    context_blocks: Optional[List[ContextBlock]] = Field(None, description="사용된 컨텍스트")
    error: Optional[str] = Field(None, description="에러 메시지")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "쿼리가 성공적으로 실행되었습니다.",
                "category": "query_request",
                "data": {"result": "..."},
                "generated_sql": "SELECT SUM(revenue) FROM sales WHERE month = '2024-01'"
            }
        }


class ChatContext(BaseModel):
    """대화 컨텍스트 모델"""
    user_id: str = Field(..., description="사용자 ID")
    context_blocks: List[ContextBlock] = Field(default_factory=list, description="컨텍스트 블록 리스트")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간")
    
    def add_block(self, block: ContextBlock):
        """컨텍스트 블록 추가"""
        self.context_blocks.append(block)
        
    def get_recent_blocks(self, limit: int = 5) -> List[ContextBlock]:
        """최근 컨텍스트 블록 조회"""
        return self.context_blocks[-limit:] if len(self.context_blocks) > limit else self.context_blocks
        
    def clear(self):
        """컨텍스트 초기화"""
        self.context_blocks = []


class StreamEvent(BaseModel):
    """SSE 스트림 이벤트 모델"""
    event: str = Field(..., description="이벤트 타입")
    data: Dict[str, Any] = Field(..., description="이벤트 데이터")
    
    def to_sse(self) -> str:
        """SSE 형식으로 변환"""
        import json
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"