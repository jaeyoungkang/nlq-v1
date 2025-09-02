"""
Abstract Base Repository interface for data access layer
Provides common interface for all repository implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from core.models import ContextBlock
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# Abstract base repository 클래스를 export
__all__ = ['BaseRepository']


class BaseRepository(ABC):
    """
    추상 기본 리포지토리 클래스
    모든 기능별 리포지토리가 상속받아 사용하는 인터페이스
    """
    
    @abstractmethod
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """
        ContextBlock을 저장
        
        Args:
            context_block: 저장할 ContextBlock 객체
            
        Returns:
            저장 결과 딕셔너리 {"success": bool, "message": str, "block_id": str}
        """
        pass
    
    @abstractmethod
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        사용자의 대화 기록을 ContextBlock 리스트로 조회
        
        Args:
            user_id: 사용자 ID
            limit: 조회 제한 개수
            
        Returns:
            조회 결과 딕셔너리 {"success": bool, "context_blocks": List[ContextBlock]}
        """
        pass
    
    @abstractmethod
    def check_user_whitelist(self, email: str, user_id: str) -> Dict[str, Any]:
        """
        사용자 화이트리스트 검증
        
        Args:
            email: 사용자 이메일
            user_id: 사용자 ID
            
        Returns:
            검증 결과 딕셔너리 {"success": bool, "allowed": bool, "user_data": dict}
        """
        pass
    
    @abstractmethod
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 데이터 저장
        
        Args:
            user_data: 저장할 사용자 데이터
            
        Returns:
            저장 결과 딕셔너리 {"success": bool, "message": str}
        """
        pass