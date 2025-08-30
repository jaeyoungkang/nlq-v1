"""
Input Classification Service - 입력 분류 전담 서비스
"""

from typing import Dict, Any, List
from core.models import ContextBlock
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class InputClassificationService:
    """입력 분류 서비스 - 사용자 입력을 카테고리별로 분류"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def classify(self, message: str, context_blocks: List[ContextBlock] = None) -> str:
        """
        사용자 입력 분류
        
        Args:
            message: 사용자 입력 메시지
            context_blocks: ContextBlock 리스트
            
        Returns:
            str: 분류 카테고리 ('query_request', 'data_analysis', 'metadata_request', etc.)
        """
        try:
            logger.info(f"🔍 입력 분류 중: {message[:50]}...")
            
            classification_result = self.llm_client.classify_input(message, context_blocks)
            category = classification_result.get("classification", {}).get("category", "query_request")
            
            logger.info(f"🏷️ 분류 결과: {category}")
            return category
            
        except Exception as e:
            logger.error(f"입력 분류 중 오류: {str(e)}")
            # 기본값으로 query_request 반환
            return "query_request"
    
    def get_classification_details(self, message: str, context_blocks: List[ContextBlock] = None) -> Dict[str, Any]:
        """
        상세한 분류 정보 반환 (디버깅/분석용)
        
        Args:
            message: 사용자 입력 메시지
            context_blocks: ContextBlock 리스트
            
        Returns:
            Dict: 전체 분류 결과
        """
        try:
            classification_result = self.llm_client.classify_input(message, context_blocks)
            return classification_result
            
        except Exception as e:
            logger.error(f"상세 분류 정보 조회 중 오류: {str(e)}")
            return {
                "classification": {"category": "query_request"},
                "confidence": 0.5,
                "error": str(e)
            }