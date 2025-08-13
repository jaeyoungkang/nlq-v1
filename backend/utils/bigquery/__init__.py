# backend/utils/bigquery/__init__.py
"""
BigQuery 서비스 패키지 초기화
분할된 BigQuery 모듈들을 통합하여 기존 인터페이스 유지 - 로그인 필수 버전 + 화이트리스트
"""

from .query_service import QueryService
from .conversation_service import ConversationService
from .user_service import UserManagementService
from typing import Dict, Any

class BigQueryClient:
    """
    통합된 BigQuery 클라이언트 - 로그인 필수 버전 + 화이트리스트
    기존 인터페이스를 유지하면서 내부적으로 분할된 서비스들을 사용
    """
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        BigQuery 클라이언트 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        
        # 각 서비스 초기화
        self.query_service = QueryService(project_id, location)
        self.conversation_service = ConversationService(project_id, location)
        self.user_service = UserManagementService(project_id, location)
        
        # 하위 호환성을 위해 client 속성 노출
        self.client = self.query_service.client
    
    # === 쿼리 관련 메서드들 ===
    
    def execute_query(self, sql_query: str, max_results: int = 1000):
        """SQL 쿼리 실행"""
        return self.query_service.execute_query(sql_query, max_results)
    
    def validate_query(self, sql_query: str):
        """SQL 쿼리 문법 검증"""
        return self.query_service.validate_query(sql_query)
    
    def get_default_table_metadata(self):
        """기본 테이블의 메타데이터 조회"""
        return self.query_service.get_default_table_metadata()
    
    # === 대화 관련 메서드들 ===
    
    def save_conversation(self, conversation_data):
        """대화 내용을 BigQuery에 저장"""
        return self.conversation_service.save_conversation(conversation_data)
    
    def get_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0):
        """인증된 사용자의 대화 히스토리 조회"""
        return self.conversation_service.get_user_conversations(user_id, limit, offset)
    
    def get_conversation_details(self, conversation_id: str, user_id: str):
        """특정 대화의 상세 내역 조회"""
        return self.conversation_service.get_conversation_details(conversation_id, user_id)
    
    def get_conversation_context(self, conversation_id: str, user_id: str, max_messages: int = 3):
        """LLM 컨텍스트용 대화 기록 조회"""
        # 이 메서드는 conversation_service에만 있으므로 직접 호출
        return self.conversation_service.get_conversation_context(conversation_id, user_id, max_messages)

    # === 쿼리 결과 저장 메서드 (수정됨) ===
    def save_query_result(self, query_id: str, result_data: Dict[str, Any]):
        """쿼리 실행 결과를 별도 테이블에 저장"""
        # conversation_service의 메서드를 올바른 인자로 호출하도록 수정
        return self.conversation_service.save_query_result(query_id, result_data)
    
    def get_query_result(self, message_id: str, user_id: str):
        """저장된 쿼리 결과 조회"""
        # 이 메서드는 conversation_service에만 있으므로 직접 호출
        return self.conversation_service.get_query_result(message_id, user_id)

    # === 사용자 화이트리스트 관리 메서드들 ===
    
    def check_user_access(self, email: str, user_id: str = None):
        """사용자 접근 권한 확인"""
        return self.user_service.check_user_access(email, user_id)
    
    def update_last_login(self, email: str):
        """사용자 마지막 로그인 시간 업데이트"""
        return self.user_service.update_last_login(email)
    
    def get_user_stats(self):
        """사용자 통계 조회 (관리자용)"""
        return self.user_service.get_user_stats()
    
    def ensure_whitelist_table_exists(self):
        """화이트리스트 테이블 존재 확인 및 생성"""
        return self.user_service.ensure_whitelist_table_exists()

__all__ = ['BigQueryClient']
