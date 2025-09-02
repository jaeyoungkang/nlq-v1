"""
Input Classification Service - 입력 분류 전담 서비스
"""

from typing import Dict, Any, List
from core.models import ContextBlock
from utils.logging_utils import get_logger
from features.llm.models import ClassificationRequest

logger = get_logger(__name__)


class InputClassificationService:
    """입력 분류 서비스 - 사용자 입력을 카테고리별로 분류"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
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
            
            # ContextBlock을 직접 LLMService에 전달
            request = ClassificationRequest(
                user_input=message,
                context_blocks=context_blocks or []
            )
            
            response = self.llm_service.classify_input(request)
            
            logger.info(f"🏷️ 분류 결과: {response.category}")
            return response.category
            
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
            # ContextBlock을 직접 LLMService에 전달
            request = ClassificationRequest(
                user_input=message,
                context_blocks=context_blocks or []
            )
            
            response = self.llm_service.classify_input(request)
            
            return {
                "classification": {"category": response.category},
                "confidence": response.confidence,
                "reasoning": response.reasoning
            }
            
        except Exception as e:
            logger.error(f"상세 분류 정보 조회 중 오류: {str(e)}")
            return {
                "classification": {"category": "query_request"},
                "confidence": 0.1,
                "error": str(e)
            }