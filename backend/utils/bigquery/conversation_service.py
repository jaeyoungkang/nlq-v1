# backend/utils/bigquery/conversation_service.py
"""
BigQuery 대화 서비스
대화 저장/조회/삭제 - 스키마 정리 계획 적용
"""

import os
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from models import ContextBlock, BlockType

logger = logging.getLogger(__name__)

class ConversationService:
    """BigQuery 대화 관리 서비스 - 스키마 정리 계획 적용"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        ConversationService 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        try:
            self.client = bigquery.Client(project=project_id, location=location)
            logger.info(f"BigQuery ConversationService 초기화 완료: {project_id}")
        except Exception as e:
            logger.error(f"BigQuery ConversationService 초기화 실패: {str(e)}")
            raise
    

    def ensure_conversations_table_exists(self) -> Dict[str, Any]:
        """대화 저장용 데이터셋/테이블 존재 확인 및 필요시 생성"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            dataset_ref = self.client.dataset(dataset_name)

            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
                logger.debug(f"📂 데이터셋 존재 확인: {dataset_name}")
            except NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "대화 저장용 데이터셋"
                self.client.create_dataset(dataset)
                logger.info(f"📂 데이터셋 자동 생성: {dataset_name}")

            # 테이블 확인/생성
            table_ref = dataset_ref.table('conversations')
            full_table_id = f"{self.project_id}.{dataset_name}.conversations"
            try:
                self.client.get_table(table_ref)
                logger.debug(f"📋 대화 테이블 존재 확인: {full_table_id}")
                return {"success": True, "action": "exists", "table_id": full_table_id}
            except NotFound:
                # 스키마 정의
                schema = [
                    bigquery.SchemaField('message_id', 'STRING', mode='REQUIRED', description='메시지 고유 ID'),
                    bigquery.SchemaField('user_id', 'STRING', mode='NULLABLE', description='사용자 ID'),
                    bigquery.SchemaField('message_type', 'STRING', mode='NULLABLE', description='메시지 유형(user/assistant/complete)'),
                    bigquery.SchemaField('message', 'STRING', mode='NULLABLE', description='사용자 질문 텍스트'),
                    bigquery.SchemaField('response', 'STRING', mode='NULLABLE', description='AI 응답 텍스트'),
                    bigquery.SchemaField('timestamp', 'TIMESTAMP', mode='REQUIRED', description='생성 시각 (UTC)'),
                    bigquery.SchemaField('generated_sql', 'STRING', mode='NULLABLE', description='생성된 SQL'),
                    bigquery.SchemaField('query_id', 'STRING', mode='NULLABLE', description='결과와 연계된 쿼리 ID'),
                    bigquery.SchemaField('context_message_ids', 'STRING', mode='REPEATED', description='연관 메시지 ID 배열'),
                    bigquery.SchemaField('result_data', 'STRING', mode='NULLABLE', description='쿼리 결과(JSON 직렬화 문자열)'),
                    bigquery.SchemaField('result_row_count', 'INT64', mode='NULLABLE', description='결과 행 수'),
                    bigquery.SchemaField('result_status', 'STRING', mode='NULLABLE', description='결과 상태(success/error)'),
                    bigquery.SchemaField('error_message', 'STRING', mode='NULLABLE', description='오류 메시지')
                ]

                table = bigquery.Table(table_ref, schema=schema)
                # 일자 파티셔닝 및 클러스터링 적용
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field='timestamp'
                )
                table.clustering_fields = ['user_id']
                table.description = '대화 메시지 저장 테이블'

                created = self.client.create_table(table)
                logger.info(f"📋 대화 테이블 생성 완료: {created.project}.{created.dataset_id}.{created.table_id}")
                return {"success": True, "action": "created", "table_id": full_table_id}
        except Exception as e:
            logger.error(f"대화 테이블 확인/생성 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}

    def save_complete_interaction(self, 
                                user_id: str, 
                                user_question: str,
                                assistant_answer: str, 
                                generated_sql: str = None,
                                query_result: dict = None,
                                context_message_ids: List[str] = None) -> Dict[str, Any]:
        """질문-답변-결과를 한 번에 저장 (통합 구조)"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            
            message_id = str(uuid.uuid4())
            current_time = datetime.now(timezone.utc)
            
            # 통합된 데이터 구조 - 계획서 기준
            interaction_data = {
                'message_id': message_id,
                'user_id': user_id,
                'message_type': 'complete',  # 질문+답변 완성형
                'message': user_question,     # 사용자 질문만
                'response': assistant_answer, # AI 응답만 (별도 필드)
                'timestamp': current_time.isoformat(),
                'generated_sql': generated_sql,
                'query_id': str(uuid.uuid4()) if query_result else None,
                'context_message_ids': context_message_ids or []
            }
            
            # 쿼리 결과 직접 포함
            if query_result:
                # result_data를 JSON 문자열로 명시적 직렬화
                result_data = query_result.get('data', [])
                interaction_data.update({
                    'result_data': json.dumps(result_data) if result_data else None,
                    'result_row_count': query_result.get('row_count', 0),
                    'result_status': 'success' if query_result.get('success') else 'error',
                    'error_message': query_result.get('error')
                })
            
            # 저장 전 테이블 확인/생성 보장
            ensure = self.ensure_conversations_table_exists()
            if not ensure.get('success'):
                return {"success": False, "error": ensure.get('error', '테이블 생성 확인 실패')}

            # 데이터베이스에 저장 - 명시적 테이블 ID 사용
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            try:
                table_ref = self.client.get_table(table_id)
            except NotFound:
                # 경합 상황 대비 재시도: 생성 후 즉시 조회 실패 시, 테이블 레퍼런스로 재시도
                table_ref = self.client.dataset(dataset_name).table('conversations')
            errors = self.client.insert_rows_json(table_ref, [interaction_data])
            
            if errors:
                logger.error(f"완전한 상호작용 저장 실패: {errors}")
                return {"success": False, "error": f"저장 중 오류 발생: {errors[0]}"}
            
            logger.info(f"💾 완전한 상호작용 저장 완료: {message_id}")
            return {"success": True, "message_id": message_id, "message": "상호작용이 성공적으로 저장되었습니다."}
            
        except Exception as e:
            logger.error(f"완전한 상호작용 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}




    def get_conversation_with_context(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """단일 쿼리로 모든 대화 기록 조회 - ContextBlock으로 반환"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            query = f"""
            SELECT 
                message_id,
                message as user_question,
                response as assistant_answer,
                generated_sql,
                result_data,
                result_row_count,
                result_status,
                timestamp,
                context_message_ids
            FROM `{table_id}`
            WHERE user_id = @user_id
            ORDER BY timestamp DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter('user_id', 'STRING', user_id),
                bigquery.ScalarQueryParameter('limit', 'INT64', limit)
            ])
            
            try:
                rows = list(self.client.query(query, job_config=job_config).result())
            except Exception as e:
                if 'not found' in str(e).lower():
                    logger.info(f"테이블이 없음. 빈 결과 반환: {table_id}")
                    return {"success": True, "context_blocks": [], "count": 0}
                raise
            
            context_blocks = []
            
            for row in rows:
                # result_data 파싱
                result_data = None
                if row.result_data:
                    try:
                        result_data = json.loads(row.result_data) if isinstance(row.result_data, str) else row.result_data
                    except (json.JSONDecodeError, TypeError):
                        result_data = row.result_data
                
                # ContextBlock 생성
                execution_result = None
                if result_data:
                    execution_result = {
                        'data': result_data,
                        'row_count': row.result_row_count or 0,
                        'generated_sql': row.generated_sql
                    }
                
                context_block = ContextBlock(
                    block_id=row.message_id,
                    user_id=user_id,
                    timestamp=row.timestamp,
                    block_type=BlockType.QUERY,
                    user_request=row.user_question or "",
                    assistant_response=row.assistant_answer or "",
                    execution_result=execution_result,
                    status="completed"
                )
                
                context_blocks.append(context_block)
            
            logger.info(f"📚 대화 기록 조회 완료: {len(context_blocks)}개 ContextBlock (user_id: {user_id})")
            return {
                "success": True, 
                "context_blocks": context_blocks,
                "count": len(context_blocks)
            }
            
        except Exception as e:
            logger.error(f"통합 대화 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "context_blocks": []}




