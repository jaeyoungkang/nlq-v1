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
    
    def save_conversation(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """대화 내용을 BigQuery에 저장"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            # 필수 필드 검증
            required_fields = ['message_id', 'message_type', 'user_id']
            if any(field not in conversation_data for field in required_fields):
                raise ValueError(f"필수 필드 누락: {required_fields}")

            # 새로운 스키마에 맞게 데이터 정리
            clean_data = self._clean_conversation_data(conversation_data)
            
            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": False, "error": table_check_result['error']}

            # 데이터 삽입 - TableReference 사용
            table_ref = self.client.dataset(dataset_name).table('conversations')
            errors = self.client.insert_rows_json(table_ref, [clean_data])
            
            if errors:
                logger.error(f"대화 저장 실패: {errors}")
                return {"success": False, "error": f"저장 중 오류 발생: {errors[0]}"}
            
            logger.info(f"💾 대화 저장 완료: {clean_data['message_id']} - {clean_data['message_type']}")
            return {"success": True, "message": "대화가 성공적으로 저장되었습니다."}
            
        except Exception as e:
            logger.error(f"대화 저장 중 오류: {str(e)}")
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
            
            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": False, "error": table_check_result['error']}
            
            message_id = str(uuid.uuid4())
            current_time = datetime.now(timezone.utc)
            
            # 통합된 데이터 구조
            interaction_data = {
                'message_id': message_id,
                'user_id': user_id,
                'message_type': 'complete',  # 질문+답변 완성형
                'message': f"Q: {user_question}\nA: {assistant_answer}",
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

    def save_query_result(self, query_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """DEPRECATED: 하위 호환성을 위해 유지 (Phase 1 완료 후 제거 예정)"""
        logger.warning("save_query_result는 deprecated입니다. save_complete_interaction을 사용하세요.")
        return {"success": True, "query_id": query_id, "message": "deprecated method called"}

            
    def get_latest_conversation(self, user_id: str) -> Dict[str, Any]:
        """DEPRECATED: get_conversation_with_context를 사용하세요"""
        logger.warning("get_latest_conversation는 deprecated입니다. get_conversation_with_context를 사용하세요.")
        return self.get_conversation_with_context(user_id, 50)

    def get_conversation_context(self, user_id: str, max_messages: int = 10) -> Dict[str, Any]:
        """LLM 컨텍스트용 대화 기록 조회 - 통합된 구조 사용"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            # 테이블 존재 확인
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": True, "context": [], "context_length": 0}
            
            # 최근 메시지들을 시간순으로 조회 (최대 max_messages개)
            query = f"""
            SELECT 
                message_id, message, timestamp,
                generated_sql, result_data, result_row_count
            FROM `{table_id}`
            WHERE user_id = @user_id
              AND message_type = 'complete'  -- 완성형 메시지만 조회
            ORDER BY timestamp DESC
            LIMIT @max_messages
            """
            
            job_config = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("max_messages", "INT64", max_messages)
            ])
            
            rows = list(self.client.query(query, job_config=job_config).result())
            
            # 시간순으로 정렬 (오래된 것부터)
            rows.reverse()
            
            context_messages = []
            for row in rows:
                # 질문과 답변 분리
                message_parts = row.message.split('\\nA: ', 1) if row.message else ['', '']
                user_question = message_parts[0].replace('Q: ', '') if len(message_parts) > 0 else ''
                assistant_answer = message_parts[1] if len(message_parts) > 1 else ''
                
                # 사용자 메시지
                if user_question:
                    context_messages.append({
                        "role": "user",
                        "content": user_question,
                        "timestamp": row.timestamp.isoformat() if row.timestamp else None
                    })
                
                # AI 응답 메시지
                if assistant_answer:
                    message_data = {
                        "role": "assistant",
                        "content": assistant_answer,
                        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                        "metadata": {
                            "generated_sql": row.generated_sql
                        }
                    }
                    
                    # 쿼리 결과 직접 포함 (통합 구조)
                    if row.result_data:
                        message_data['query_result_data'] = row.result_data
                        message_data['query_row_count'] = row.result_row_count
                        logger.info(f"📊 컨텍스트에 쿼리 결과 포함: {row.result_row_count}행")
                    
                    context_messages.append(message_data)
            
            logger.info(f"📚 컨텍스트 조회 완료: {len(context_messages)}개 메시지 (user_id: {user_id})")
            
            return {
                "success": True,
                "context": context_messages,
                "context_length": len(context_messages)
            }
            
        except Exception as e:
            logger.error(f"컨텍스트 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "context": [], "context_length": 0}

    def _get_query_results_by_ids(self, query_ids: List[str], dataset_name: str) -> Dict[str, Any]:
        """DEPRECATED: 통합 구조에서는 더 이상 필요하지 않음"""
        logger.warning("_get_query_results_by_ids는 deprecated입니다. 통합 구조를 사용하세요.")
        return {}

    def get_conversation_with_context(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """단일 쿼리로 모든 대화 기록 조회 - JOIN 없음"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            # 테이블 존재 확인
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": True, "conversations": [], "count": 0}
            
            query = f"""
            SELECT 
                message_id,
                message,
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
                    "message": row.message,
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

    def _clean_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """저장을 위해 대화 데이터 정리"""
        cleaned_data = {
            'message_id': data.get('message_id'),
            'user_id': data.get('user_id'),
            'message_type': data.get('message_type'),
            'message': data.get('message'),
            'timestamp': data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'generated_sql': data.get('generated_sql'),
            'query_id': data.get('query_id')
        }
        
        # 통합 구조 컬럼들 추가
        if 'result_data' in data:
            cleaned_data['result_data'] = data['result_data']
        if 'result_row_count' in data:
            cleaned_data['result_row_count'] = data['result_row_count']
        if 'result_status' in data:
            cleaned_data['result_status'] = data['result_status']
        if 'error_message' in data:
            cleaned_data['error_message'] = data['error_message']
        if 'context_message_ids' in data:
            cleaned_data['context_message_ids'] = data['context_message_ids']
            
        return cleaned_data

    def _ensure_table_exists(self, dataset_name: str, table_name: str, create_method: callable) -> Dict[str, Any]:
        """테이블 존재 확인 및 생성 헬퍼"""
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

    def _create_query_results_table(self, dataset_name: str) -> Dict[str, Any]:
        """새로운 스키마로 query_results 테이블 생성"""
        table_id = f"{self.project_id}.{dataset_name}.query_results"
        try:
            schema = [
                bigquery.SchemaField("query_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("result_payload", "STRING"), # JSON as STRING
                bigquery.SchemaField("creation_time", "TIMESTAMP", mode="REQUIRED"),
            ]
            table = bigquery.Table(table_id, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="creation_time")
            self.client.create_table(table)
            logger.info(f"테이블 생성 완료: {table_id}")
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