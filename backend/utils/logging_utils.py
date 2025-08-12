"""
표준화된 로깅 유틸리티
일관된 로깅 스타일과 이모지 사용 규칙 제공
"""

import logging
from typing import Any, Optional

class StandardLogger:
    """표준화된 로깅 패턴을 제공하는 클래스"""
    
    def __init__(self, logger_name: str):
        """
        표준 로거 초기화
        
        Args:
            logger_name: 로거 이름 (보통 __name__ 사용)
        """
        self.logger = logging.getLogger(logger_name)
    
    # === 성공/완료 로그 ===
    def success(self, message: str, **kwargs):
        """성공 로그 (INFO 레벨)"""
        self.logger.info(f"✅ {message}", **kwargs)
    
    def completed(self, message: str, **kwargs):
        """완료 로그 (INFO 레벨)"""
        self.logger.info(f"🎯 {message}", **kwargs)
    
    def created(self, message: str, **kwargs):
        """생성 완료 로그 (INFO 레벨)"""
        self.logger.info(f"🔧 {message}", **kwargs)
    
    def saved(self, message: str, **kwargs):
        """저장 완료 로그 (INFO 레벨)"""
        self.logger.info(f"💾 {message}", **kwargs)
    
    # === 진행/처리 로그 ===
    def processing(self, message: str, **kwargs):
        """처리 중 로그 (INFO 레벨)"""
        self.logger.info(f"⚡ {message}", **kwargs)
    
    def loading(self, message: str, **kwargs):
        """로딩 중 로그 (INFO 레벨)"""
        self.logger.info(f"🔄 {message}", **kwargs)
    
    def authenticating(self, message: str, **kwargs):
        """인증 처리 로그 (INFO 레벨)"""
        self.logger.info(f"🔐 {message}", **kwargs)
    
    def querying(self, message: str, **kwargs):
        """쿼리 실행 로그 (INFO 레벨)"""
        self.logger.info(f"📊 {message}", **kwargs)
    
    # === 경고 로그 ===
    def warning(self, message: str, **kwargs):
        """경고 로그 (WARNING 레벨)"""
        self.logger.warning(f"⚠️ {message}", **kwargs)
    
    def access_denied(self, message: str, **kwargs):
        """접근 거부 로그 (WARNING 레벨)"""
        self.logger.warning(f"🚫 {message}", **kwargs)
    
    def deprecated(self, message: str, **kwargs):
        """deprecated 경고 로그 (WARNING 레벨)"""
        self.logger.warning(f"🔄 [DEPRECATED] {message}", **kwargs)
    
    # === 에러 로그 ===
    def error(self, message: str, **kwargs):
        """에러 로그 (ERROR 레벨)"""
        self.logger.error(f"❌ {message}", **kwargs)
    
    def critical(self, message: str, **kwargs):
        """치명적 에러 로그 (CRITICAL 레벨)"""
        self.logger.critical(f"🚨 {message}", **kwargs)
    
    def auth_error(self, message: str, **kwargs):
        """인증 에러 로그 (ERROR 레벨)"""
        self.logger.error(f"🔐❌ {message}", **kwargs)
    
    def db_error(self, message: str, **kwargs):
        """데이터베이스 에러 로그 (ERROR 레벨)"""
        self.logger.error(f"🗄️❌ {message}", **kwargs)
    
    # === 정보/디버그 로그 ===
    def info(self, message: str, **kwargs):
        """일반 정보 로그 (INFO 레벨)"""
        self.logger.info(f"ℹ️ {message}", **kwargs)
    
    def debug(self, message: str, **kwargs):
        """디버그 로그 (DEBUG 레벨)"""
        self.logger.debug(f"🔍 {message}", **kwargs)
    
    def stats(self, message: str, **kwargs):
        """통계 정보 로그 (INFO 레벨)"""
        self.logger.info(f"📈 {message}", **kwargs)
    
    def config(self, message: str, **kwargs):
        """설정 정보 로그 (INFO 레벨)"""
        self.logger.info(f"⚙️ {message}", **kwargs)
    
    # === 특수 목적 로그 ===
    def startup(self, message: str, **kwargs):
        """시작 로그 (INFO 레벨)"""
        self.logger.info(f"🚀 {message}", **kwargs)
    
    def shutdown(self, message: str, **kwargs):
        """종료 로그 (INFO 레벨)"""
        self.logger.info(f"🛑 {message}", **kwargs)
    
    def cleanup(self, message: str, **kwargs):
        """정리 작업 로그 (INFO 레벨)"""
        self.logger.info(f"🧹 {message}", **kwargs)
    
    def user_action(self, message: str, **kwargs):
        """사용자 액션 로그 (INFO 레벨)"""
        self.logger.info(f"👤 {message}", **kwargs)
    
    # === 원본 로거 메서드 접근 ===
    def raw_log(self, level: int, message: str, **kwargs):
        """이모지 없는 원본 로그"""
        self.logger.log(level, message, **kwargs)

def get_logger(name: str) -> StandardLogger:
    """
    표준 로거 팩토리 함수
    
    Args:
        name: 로거 이름 (보통 __name__ 사용)
        
    Returns:
        StandardLogger 인스턴스
    """
    return StandardLogger(name)

# 하위 호환성을 위한 별칭들
def log_success(logger: logging.Logger, message: str):
    """하위 호환성용 성공 로그 (deprecated)"""
    logger.info(f"✅ {message}")

def log_error(logger: logging.Logger, message: str):
    """하위 호환성용 에러 로그 (deprecated)"""
    logger.error(f"❌ {message}")

def log_warning(logger: logging.Logger, message: str):
    """하위 호환성용 경고 로그 (deprecated)"""
    logger.warning(f"⚠️ {message}")