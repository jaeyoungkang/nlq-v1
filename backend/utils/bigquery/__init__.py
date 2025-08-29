# backend/utils/bigquery/__init__.py
"""
BigQuery 서비스 패키지 초기화
분할된 BigQuery 모듈들을 통합하여 핵심 기능 제공 - 로그인 필수 버전 + 화이트리스트
"""

from .query_service import QueryService
from .conversation_service import ConversationService
from .user_service import UserManagementService
from typing import Dict, Any

class BigQueryClient:
    """
    통합된 BigQuery 클라이언트 - 로그인 필수 버전 + 화이트리스트
    핵심 기능에 집중된 깔끔한 인터페이스 제공
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
    
    
    # === 대화 관련 메서드들 ===
    
    
    
    def get_conversation_with_context(self, user_id: str, limit: int = 10):
        """단일 쿼리로 모든 대화 기록 조회 - JOIN 없음"""
        return self.conversation_service.get_conversation_with_context(user_id, limit)
    
    def save_complete_interaction(self, user_id: str, user_question: str, assistant_answer: str, 
                                generated_sql: str = None, query_result: dict = None, 
                                context_message_ids: list = None):
        """질문-답변-결과를 한 번에 저장 (통합 구조)"""
        return self.conversation_service.save_complete_interaction(
            user_id, user_question, assistant_answer, generated_sql, 
            query_result, context_message_ids
        )


    # === 쿼리 결과 저장 메서드 (수정됨) ===
    def save_query_result(self, query_id: str, result_data: Dict[str, Any]):
        """쿼리 실행 결과를 별도 테이블에 저장"""
        # conversation_service의 메서드를 올바른 인자로 호출하도록 수정
        return self.conversation_service.save_query_result(query_id, result_data)
    

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

    def ensure_conversations_table_exists(self):
        """대화 테이블 존재 확인 및 생성"""
        return self.conversation_service.ensure_conversations_table_exists()

__all__ = ['BigQueryClient']
