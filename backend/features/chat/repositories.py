"""
Chat Repository
대화 관련 데이터 접근 계층 - 대화 저장/조회, 컨텍스트 관리
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from core.repositories.base import BaseRepository, bigquery, NotFound
from core.models import ContextBlock, BlockType
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class ChatRepository(BaseRepository):
    """대화 관련 데이터 접근 계층"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        super().__init__(
            table_name="conversations", 
            dataset_name="v1", 
            project_id=project_id, 
            location=location
        )
    
    def ensure_table_exists(self) -> Dict[str, Any]:
        """conversations 테이블 존재 확인 및 기존 스키마로 생성"""
        try:
            dataset_ref = self.client.dataset(self.dataset_name)
            
            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
            except NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "NLQ-v1 conversations dataset"
                self.client.create_dataset(dataset)
                logger.info(f"데이터셋 생성: {self.dataset_name}")
            
            # 테이블 확인/생성
            table_ref = dataset_ref.table(self.table_name)
            try:
                self.client.get_table(table_ref)
                return {"success": True, "action": "exists", "table_id": self.table_id}
            except NotFound:
                # ContextBlock 모델과 완전 매칭되는 스키마로 테이블 생성
                schema = [
                    bigquery.SchemaField("block_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"), 
                    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("block_type", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_request", "STRING", mode="REQUIRED"),  # ContextBlock에서 필수 필드
                    bigquery.SchemaField("assistant_response", "STRING", mode="NULLABLE"),  # 기본값 ""
                    bigquery.SchemaField("generated_query", "STRING", mode="NULLABLE"),  # 생성된 쿼리 (별도 필드)
                    bigquery.SchemaField("execution_result", "JSON", mode="NULLABLE"),  # 기본값 None
                    bigquery.SchemaField("status", "STRING", mode="REQUIRED")  # 기본값 "pending"
                ]
                
                table = bigquery.Table(table_ref, schema=schema)
                table.description = "Conversation history and context blocks"
                self.client.create_table(table)
                
                logger.info(f"conversations 테이블 생성 완료: {self.table_id}")
                return {"success": True, "action": "created", "table_id": self.table_id}
                
        except Exception as e:
            logger.error(f"conversations 테이블 확인/생성 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
        
    def get_conversation_with_context(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자의 최근 대화 기록을 ContextBlock 형태로 조회"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            # 새로운 block 기반 스키마 쿼리
            query = f"""
            SELECT 
                block_id,
                user_id,
                timestamp,
                block_type,
                user_request,
                assistant_response,
                generated_query,
                execution_result,
                status
            FROM `{self.table_id}`
            WHERE user_id = @user_id
            ORDER BY timestamp DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig()
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter('user_id', 'STRING', user_id),
                bigquery.ScalarQueryParameter('limit', 'INT64', limit)
            ]
            
            # 테이블 존재 확인 및 생성 (BaseRepository 메서드 사용)
            ensure_result = self.ensure_table_exists()
            if not ensure_result.get('success'):
                logger.warning(f"conversations 테이블 확인 실패: {ensure_result.get('error')}")
                return {'success': True, 'context_blocks': []}
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            context_blocks = []
            for row in results:
                try:
                    # execution_result JSON 파싱
                    execution_result = None
                    if row.execution_result:
                        import json
                        execution_result = json.loads(row.execution_result) if isinstance(row.execution_result, str) else row.execution_result
                    
                    context_block = ContextBlock(
                        block_id=row.block_id,
                        user_id=row.user_id,
                        timestamp=row.timestamp,
                        block_type=BlockType(row.block_type) if row.block_type else BlockType.QUERY,
                        user_request=row.user_request or "",
                        assistant_response=row.assistant_response or "",
                        generated_query=row.generated_query,
                        execution_result=execution_result,
                        status=row.status or "completed"
                    )
                    context_blocks.append(context_block)
                    
                except Exception as row_error:
                    logger.warning(f"행 처리 중 오류 (건너뜀): {str(row_error)}")
                    continue
            
            logger.info(f"대화 컨텍스트 조회 완료: {len(context_blocks)}개 블록")
            return {'success': True, 'context_blocks': context_blocks}
            
        except Exception as e:
            logger.error(f"대화 컨텍스트 조회 중 예외: {str(e)}")
            return {'success': False, 'error': f'대화 컨텍스트 조회 오류: {str(e)}'}
    
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock을 BigQuery에 저장"""
        try:
            if not self.client:
                return {'success': False, 'error': 'BigQuery 클라이언트 없음'}
            
            # ContextBlock을 딕셔너리로 변환
            block_data = context_block.to_dict()
            
            # execution_result JSON 직렬화
            if block_data.get('execution_result'):
                import json
                block_data['execution_result'] = json.dumps(block_data['execution_result'])
            
            # BaseRepository의 save 메서드 사용
            result = self.save(block_data)
            
            if result.get('success'):
                logger.info(f"ContextBlock 저장 완료: {context_block.block_id}")
                return {'success': True, 'block_id': context_block.block_id, 'message': 'ContextBlock이 성공적으로 저장되었습니다'}
            else:
                logger.error(f"ContextBlock 저장 실패: {result.get('error')}")
                return result
                
        except Exception as e:
            logger.error(f"ContextBlock 저장 중 오류: {str(e)}")
            return {'success': False, 'error': f'ContextBlock 저장 실패: {str(e)}'}
                
