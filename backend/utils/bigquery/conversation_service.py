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
            
            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": False, "error": table_check_result['error']}
            
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
                interaction_data.update({
                    'result_data': query_result.get('data', []),
                    'result_row_count': query_result.get('row_count', 0),
                    'result_status': 'success' if query_result.get('success') else 'error',
                    'error_message': query_result.get('error')
                })
            
            # 데이터베이스에 저장
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
        """단일 쿼리로 모든 대화 기록 조회 - JOIN 없음"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                logger.info(f"테이블이 없거나 생성 실패. 빈 결과 반환: {table_check_result.get('error')}")
                return {"success": True, "conversations": [], "count": 0}
            
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
            
            rows = list(self.client.query(query, job_config=job_config).result())
            
            conversations = []
            for row in rows:
                conv_data = {
                    "message_id": row.message_id,
                    "user_question": row.user_question,      # 계획서 기준
                    "assistant_answer": row.assistant_answer, # 계획서 기준
                    "generated_sql": row.generated_sql,
                    "result_row_count": row.result_row_count,
                    "result_status": row.result_status,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "context_message_ids": list(row.context_message_ids) if row.context_message_ids else []
                }
                
                # result_data가 있으면 포함
                if row.result_data:
                    conv_data["result_data"] = row.result_data
                    
                conversations.append(conv_data)
            
            logger.info(f"📚 단일 쿼리로 대화 기록 조회 완료: {len(conversations)}개 (user_id: {user_id})")
            return {"success": True, "conversations": conversations, "count": len(conversations)}
            
        except Exception as e:
            logger.error(f"통합 대화 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "conversations": []}


    def _ensure_table_exists(self, dataset_name: str, table_name: str, create_method: callable) -> Dict[str, Any]:
        """테이블 존재 확인 및 생성 헬퍼"""
        try:
            # 먼저 데이터셋이 있는지 확인
            dataset_ref = self.client.dataset(dataset_name)
            try:
                self.client.get_dataset(dataset_ref)
            except NotFound:
                # 데이터셋이 없으면 생성
                logger.info(f"데이터셋 {dataset_name} 없음. 생성 시도.")
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                try:
                    self.client.create_dataset(dataset)
                    logger.info(f"데이터셋 {dataset_name} 생성 완료")
                except Exception as e:
                    if 'Already exists' not in str(e):
                        logger.error(f"데이터셋 생성 실패: {e}")
                        return {"success": False, "error": f"데이터셋 생성 실패: {str(e)}"}
            
            # 테이블 존재 확인
            table_ref = self.client.dataset(dataset_name).table(table_name)
            try:
                self.client.get_table(table_ref)
                return {"success": True, "action": "exists"}
            except NotFound:
                logger.info(f"테이블 {table_name} 없음. 생성 시도.")
                result = create_method(dataset_name)
                # 동시 생성으로 인한 Already Exists 에러는 성공으로 처리
                if not result['success'] and 'Already Exists' in result.get('error', ''):
                    logger.info(f"테이블 {table_name} 이미 존재함 (동시 생성됨)")
                    return {"success": True, "action": "exists"}
                return result
        except Exception as e:
            logger.error(f"테이블 확인/생성 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}

    def _create_conversations_table(self, dataset_name: str) -> Dict[str, Any]:
        """통합 구조의 conversations 테이블 생성"""
        table_id = f"{self.project_id}.{dataset_name}.conversations"
        try:
            schema = [
                # 기본 필드
                bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message", "STRING"),
                bigquery.SchemaField("response", "STRING"),  # AI 응답 전용 필드 추가
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("generated_sql", "STRING"),
                bigquery.SchemaField("query_id", "STRING"),
                
                # 통합 구조 - 결과 데이터 컬럼들
                bigquery.SchemaField("result_data", "JSON"),
                bigquery.SchemaField("result_row_count", "INT64"),
                bigquery.SchemaField("result_status", "STRING"),
                bigquery.SchemaField("error_message", "STRING"),
                bigquery.SchemaField("context_message_ids", "STRING", mode="REPEATED")
            ]
            table = bigquery.Table(table_id, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="timestamp")
            self.client.create_table(table)
            logger.info(f"통합 구조 테이블 생성 완료: {table_id}")
            return {"success": True, "action": "created"}
        except Exception as e:
            logger.error(f"테이블 생성 실패 {table_id}: {e}")
            return {"success": False, "error": str(e)}


    def get_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """사용자의 대화 히스토리 목록 조회 - 단일 쓰레드 모델"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": True, "conversations": [], "count": 0}
            
            query = f"""
            SELECT 
                MIN(timestamp) as start_time,
                MAX(timestamp) as last_time,
                COUNT(*) as message_count,
                ARRAY_AGG(
                    CASE WHEN message_type = 'user' THEN message ELSE NULL END IGNORE NULLS
                    ORDER BY timestamp 
                    LIMIT 1
                )[SAFE_OFFSET(0)] as first_message
            FROM `{conversations_table}`
            WHERE user_id = @user_id
            """
            job_config = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ])
            
            results = self.client.query(query, job_config=job_config).result()
            row = next(iter(results), None)
            
            conversations = []
            if row and row.message_count > 0:
                conversations = [{
                    "user_id": user_id,
                    "start_time": row.start_time.isoformat() if row.start_time else None,
                    "last_time": row.last_time.isoformat() if row.last_time else None,
                    "message_count": row.message_count,
                    "first_message": row.first_message or "대화 없음"
                }]
            
            return {"success": True, "conversations": conversations, "count": len(conversations)}
        except Exception as e:
            logger.error(f"대화 히스토리 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "conversations": []}