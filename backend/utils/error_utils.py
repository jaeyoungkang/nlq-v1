"""
공통 에러 응답 유틸리티
표준화된 에러 응답 생성 및 로깅 기능 제공
"""

import logging
import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ErrorResponse:
    """표준화된 에러 응답 생성 클래스"""
    
    @staticmethod
    def create(
        error_message: str, 
        error_type: str = "general", 
        details: Optional[Dict[str, Any]] = None,
        log_error: bool = True
    ) -> Dict[str, Any]:
        """
        표준화된 에러 응답 생성
        
        Args:
            error_message: 에러 메시지
            error_type: 에러 타입
            details: 추가 상세 정보
            log_error: 에러 로깅 여부
            
        Returns:
            표준 에러 응답 딕셔너리
        """
        if log_error:
            logger.error(f"❌ {error_type}: {error_message}")
        
        return {
            "success": False,
            "error": error_message,
            "error_type": error_type,
            "details": details or {},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    
    @staticmethod
    def validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """입력 검증 에러 응답"""
        return ErrorResponse.create(message, "validation_error", details)
    
    @staticmethod
    def service_error(
        message: str, 
        service: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """서비스 에러 응답"""
        error_details = {"service": service}
        if details:
            error_details.update(details)
        return ErrorResponse.create(message, "service_error", error_details)
    
    @staticmethod
    def internal_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """내부 서버 에러 응답"""
        return ErrorResponse.create(message, "internal_error", details)
    
    @staticmethod
    def auth_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """인증 에러 응답"""
        return ErrorResponse.create(message, "auth_error", details)
    
    @staticmethod
    def permission_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """권한 에러 응답"""
        return ErrorResponse.create(message, "permission_error", details)
    
    @staticmethod
    def not_found_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """리소스 없음 에러 응답"""
        return ErrorResponse.create(message, "not_found", details)

class SuccessResponse:
    """표준화된 성공 응답 생성 클래스"""
    
    @staticmethod
    def create(
        message: str = "요청이 성공적으로 처리되었습니다",
        data: Optional[Any] = None,
        log_success: bool = False
    ) -> Dict[str, Any]:
        """
        표준화된 성공 응답 생성
        
        Args:
            message: 성공 메시지
            data: 응답 데이터
            log_success: 성공 로깅 여부
            
        Returns:
            표준 성공 응답 딕셔너리
        """
        if log_success:
            logger.info(f"✅ {message}")
        
        response = {
            "success": True,
            "message": message,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        if data is not None:
            response["data"] = data
            
        return response

# 하위 호환성을 위한 별칭
def create_error_response(error_message: str, error_type: str = "general", details: Dict[str, Any] = None):
    """하위 호환성을 위한 함수 (deprecated)"""
    logger.warning("⚠️ create_error_response는 deprecated입니다. ErrorResponse.create()를 사용하세요.")
    return ErrorResponse.create(error_message, error_type, details)