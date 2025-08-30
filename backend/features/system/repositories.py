"""
System Repository
시스템 관리 관련 데이터 접근 계층 - 통계, 스키마 정보 등
"""

from typing import Dict, Any, Optional
from core.repositories.base import BaseRepository, bigquery, NotFound
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class SystemRepository(BaseRepository):
    """시스템 관리 관련 데이터 접근 계층"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        super().__init__(
            table_name="system_info", 
            dataset_name="v1", 
            project_id=project_id, 
            location=location
        )
        
    def get_user_stats(self) -> Dict[str, Any]:
        """사용자 통계 조회 (관리자용)"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            # 화이트리스트 테이블에서 사용자 통계 조회
            whitelist_table_id = f"{self.project_id}.{self.dataset_name}.users_whitelist"
            
            query = f"""
            SELECT 
                COUNT(*) as total_users,
                COUNTIF(status = 'active') as active_users,
                COUNTIF(status = 'inactive') as inactive_users,
                COUNTIF(status = 'pending') as pending_users
            FROM `{whitelist_table_id}`
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            for row in results:
                stats = {
                    'total_users': row.total_users,
                    'by_status': {
                        'active': row.active_users,
                        'inactive': row.inactive_users,
                        'pending': row.pending_users
                    }
                }
                return {'success': True, 'stats': stats}
            
            return {'success': True, 'stats': {'total_users': 0, 'by_status': {}}}
            
        except Exception as e:
            logger.error(f"❌ 사용자 통계 조회 중 예외: {str(e)}")
            return {'success': False, 'error': f'사용자 통계 조회 오류: {str(e)}'}
    
    def ensure_whitelist_table_exists(self) -> Dict[str, Any]:
        """화이트리스트 테이블 존재 확인 및 생성"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
                
            dataset_ref = self.client.dataset(self.dataset_name)
            
            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
                logger.debug(f"데이터셋 확인: {self.dataset_name}")
            except NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "NLQ-v1 system dataset"
                self.client.create_dataset(dataset)
                logger.info(f"데이터셋 생성: {self.dataset_name}")
            
            # 화이트리스트 테이블 확인/생성
            whitelist_table_name = "users_whitelist"
            table_ref = dataset_ref.table(whitelist_table_name)
            whitelist_table_id = f"{self.project_id}.{self.dataset_name}.{whitelist_table_name}"
            
            try:
                self.client.get_table(table_ref)
                logger.debug(f"화이트리스트 테이블 확인: {whitelist_table_id}")
                return {"success": True, "action": "exists", "table_id": whitelist_table_id}
            except NotFound:
                # 화이트리스트 테이블 스키마 정의
                schema = [
                    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("email", "STRING", mode="REQUIRED"), 
                    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
                ]
                
                table = bigquery.Table(table_ref, schema=schema)
                table.description = "User whitelist for access control"
                table = self.client.create_table(table)
                
                logger.info(f"화이트리스트 테이블 생성 완료: {whitelist_table_id}")
                return {"success": True, "action": "created", "table_id": whitelist_table_id}
            
        except Exception as e:
            logger.error(f"❌ 화이트리스트 테이블 확인 중 오류: {str(e)}")
            return {'success': False, 'error': f'화이트리스트 테이블 확인 실패: {str(e)}'}
            
    def ensure_conversations_table_exists(self) -> Dict[str, Any]:
        """대화 테이블 존재 확인 및 생성"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
                
            logger.info("대화 테이블은 ChatRepository에서 관리됩니다")
            return {'success': True, 'message': 'ChatRepository에서 처리됩니다'}
            
        except Exception as e:
            logger.error(f"대화 테이블 확인 중 오류: {str(e)}")
            return {'success': False, 'error': f'대화 테이블 확인 실패: {str(e)}'}
    
    def get_conversation_table_schemas(self) -> Dict[str, Any]:
        """대화 테이블 스키마 정보 조회"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
                
            # 대화 테이블 스키마 조회
            conversation_table_id = f"{self.project_id}.{self.dataset_name}.conversations"
            
            try:
                table = self.client.get_table(conversation_table_id)
                schema_fields = []
                
                for field in table.schema:
                    schema_fields.append({
                        'name': field.name,
                        'type': field.field_type,
                        'mode': field.mode,
                        'description': field.description or ''
                    })
                
                return {
                    'success': True,
                    'schemas': {
                        'conversations': {
                            'table_id': conversation_table_id,
                            'fields': schema_fields,
                            'description': table.description or ''
                        }
                    }
                }
                
            except NotFound:
                return {
                    'success': False,
                    'error': f'대화 테이블을 찾을 수 없습니다: {conversation_table_id}'
                }
            
        except Exception as e:
            logger.error(f"❌ 대화 테이블 스키마 조회 중 오류: {str(e)}")
            return {'success': False, 'error': f'스키마 조회 실패: {str(e)}'}