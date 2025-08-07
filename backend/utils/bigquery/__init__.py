"""
BigQuery 서비스 패키지 초기화
분할된 BigQuery 모듈들을 통합하여 기존 인터페이스 유지 - 로그인 필수 버전
"""

from .query_service import QueryService
from .conversation_service import ConversationService

class BigQueryClient:
    """
    통합된 BigQuery 클라이언트 - 로그인 필수 버전
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
        
        # 각 서비스 초기화 (사용량 서비스 제거)
        self.query_service = QueryService(project_id, location)
        self.conversation_service = ConversationService(project_id, location)
        
        # 하위 호환성을 위해 client 속성 노출
        self.client = self.query_service.client
    
    # === 쿼리 관련 메서드들 ===
    
    def execute_query(self, sql_query: str, max_results: int = 1000):
        """SQL 쿼리 실행"""
        return self.query_service.execute_query(sql_query, max_results)
    
    def validate_query(self, sql_query: str):
        """SQL 쿼리 문법 검증"""
        return self.query_service.validate_query(sql_query)
    
    def list_datasets(self):
        """프로젝트의 데이터셋 목록 조회"""
        return self.query_service.list_datasets()
    
    def list_tables(self, dataset_id: str):
        """데이터셋의 테이블 목록 조회"""
        return self.query_service.list_tables(dataset_id)
    
    def get_table_schema(self, dataset_id: str, table_id: str):
        """테이블 스키마 정보 조회"""
        return self.query_service.get_table_schema(dataset_id, table_id)
    
    def get_default_table_metadata(self):
        """기본 테이블의 메타데이터 조회"""
        return self.query_service.get_default_table_metadata()
    
    def format_bytes(self, bytes_count: int):
        """바이트 수를 읽기 쉬운 형태로 포맷"""
        return self.query_service.format_bytes(bytes_count)
    
    # === 대화 관련 메서드들 ===
    
    def save_conversation(self, conversation_data):
        """대화 내용을 BigQuery에 저장 (로그인 사용자 전용)"""
        return self.conversation_service.save_conversation(conversation_data)
    
    def get_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0):
        """인증된 사용자의 대화 히스토리 조회"""
        return self.conversation_service.get_user_conversations(user_id, limit, offset)
    
    def get_conversation_details(self, conversation_id: str, user_id: str):
        """특정 대화의 상세 내역 조회 (사용자 권한 확인 포함)"""
        return self.conversation_service.get_conversation_details(conversation_id, user_id)
    
    def delete_conversation(self, conversation_id: str, user_id: str):
        """사용자의 특정 대화 삭제"""
        return self.conversation_service.delete_conversation(conversation_id, user_id)
        
    def link_session_to_user(self, session_id: str, user_id: str, user_email: str):
        """세션 ID의 모든 대화를 사용자 계정으로 연결 (로그인 시 사용)"""
        return self.conversation_service.link_session_to_user(session_id, user_id, user_email)

__all__ = ['BigQueryClient']