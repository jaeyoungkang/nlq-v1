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
            required_fields = ['conversation_id', 'message_id', 'message_type', 'user_id']
            if any(field not in conversation_data for field in required_fields):
                raise ValueError(f"필수 필드 누락: {required_fields}")

            # 새로운 스키마에 맞게 데이터 정리
            clean_data = self._clean_conversation_data(conversation_data)
            
            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": False, "error": table_check_result['error']}

            # 데이터 삽입
            errors = self.client.insert_rows_json(table_id, [clean_data])
            
            if errors:
                logger.error(f"대화 저장 실패: {errors}")
                return {"success": False, "error": f"저장 중 오류 발생: {errors[0]}"}
            
            logger.info(f"💾 대화 저장 완료: {clean_data['conversation_id']} - {clean_data['message_type']}")
            return {"success": True, "message": "대화가 성공적으로 저장되었습니다."}
            
        except Exception as e:
            logger.error(f"대화 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}

    def save_query_result(self, query_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """쿼리 실행 결과를 'query_results' 테이블에 저장"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_id = f"{self.project_id}.{dataset_name}.query_results"

            # 테이블 존재 확인 및 생성
            table_check_result = self._ensure_table_exists(dataset_name, 'query_results', self._create_query_results_table)
            if not table_check_result['success']:
                return {"success": False, "error": table_check_result['error']}

            # result_payload JSON 객체 생성
            payload = {
                "status": "success" if result_data.get("success", False) else "error",
                "metadata": {
                    "row_count": result_data.get("row_count"),
                    "data_size_kb": len(json.dumps(result_data.get("data", []))) / 1024,
                    "is_summary": len(result_data.get("data", [])) < result_data.get("row_count", 0),
                    "schema": [{"name": k, "type": str(type(v).__name__)} for k, v in result_data.get("data", [{}])[0].items()] if result_data.get("data") else []
                },
                "data": result_data.get("data", []),
                "error": result_data.get("error")
            }

            # 삽입할 행 데이터
            row_to_insert = {
                "query_id": query_id,
                "result_payload": json.dumps(payload, default=str),
                "creation_time": datetime.now(timezone.utc).isoformat()
            }

            errors = self.client.insert_rows_json(table_id, [row_to_insert])
            if errors:
                logger.error(f"쿼리 결과 저장 실패: {errors}")
                return {"success": False, "error": f"쿼리 결과 저장 실패: {errors[0]}"}

            logger.info(f"📊 쿼리 결과 저장 완료: {query_id}")
            return {"success": True, "query_id": query_id}

        except Exception as e:
            logger.error(f"❌ 쿼리 결과 저장 중 오류: {str(e)}")
            return {"success": False, "error": f"쿼리 결과 저장 오류: {str(e)}"}

    def get_conversation_details(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """특정 대화의 상세 내역 및 관련 쿼리 결과 조회"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conv_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 1. 대화 내용 조회
            query = f"""
            SELECT 
                c.message_id, c.message, c.message_type, c.timestamp,
                c.generated_sql, c.query_id
            FROM `{conv_table}` AS c
            WHERE c.conversation_id = @conversation_id AND c.user_id = @user_id
            ORDER BY c.timestamp ASC
            """
            job_config = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ])
            
            rows = list(self.client.query(query, job_config=job_config).result())
            
            # 2. 쿼리 결과 일괄 조회
            query_ids = [row.query_id for row in rows if row.query_id]
            query_results_map = self._get_query_results_by_ids(query_ids, dataset_name)

            # 3. 대화와 쿼리 결과 결합
            messages = []
            for row in rows:
                message_data = {
                    "message_id": row.message_id,
                    "message": row.message,
                    "message_type": row.message_type,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "generated_sql": row.generated_sql,
                }
                
                if row.query_id in query_results_map:
                    payload = query_results_map[row.query_id]
                    if payload.get("status") == "success":
                        message_data['query_result_data'] = payload.get('data')
                        message_data['query_row_count'] = payload.get('metadata', {}).get('row_count')

                messages.append(message_data)
            
            return {"success": True, "messages": messages, "message_count": len(messages)}

        except Exception as e:
            logger.error(f"대화 상세 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "messages": []}

    def _get_query_results_by_ids(self, query_ids: List[str], dataset_name: str) -> Dict[str, Any]:
        """ID 목록으로 쿼리 결과 페이로드 조회"""
        if not query_ids:
            return {}
        
        results_table = f"{self.project_id}.{dataset_name}.query_results"
        query = f"""
            SELECT query_id, result_payload
            FROM `{results_table}`
            WHERE query_id IN UNNEST(@query_ids)
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("query_ids", "STRING", query_ids)
        ])
        
        rows = self.client.query(query, job_config=job_config).result()
        
        results_map = {}
        for row in rows:
            try:
                results_map[row.query_id] = json.loads(row.result_payload)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"결과 페이로드 파싱 실패: query_id={row.query_id}")
                results_map[row.query_id] = {"error": "payload parsing failed"}
        return results_map

    def _clean_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """저장을 위해 대화 데이터 정리"""
        return {
            'conversation_id': data.get('conversation_id'),
            'message_id': data.get('message_id'),
            'user_id': data.get('user_id'),
            'message_type': data.get('message_type'),
            'message': data.get('message'),
            'timestamp': data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'generated_sql': data.get('generated_sql'),
            'query_id': data.get('query_id')
        }

    def _ensure_table_exists(self, dataset_name: str, table_name: str, create_method: callable) -> Dict[str, Any]:
        """테이블 존재 확인 및 생성 헬퍼"""
        table_ref = self.client.dataset(dataset_name).table(table_name)
        try:
            self.client.get_table(table_ref)
            return {"success": True, "action": "exists"}
        except NotFound:
            logger.info(f"테이블 {table_name} 없음. 생성 시도.")
            return create_method(dataset_name)

    def _create_conversations_table(self, dataset_name: str) -> Dict[str, Any]:
        """새로운 스키마로 conversations 테이블 생성"""
        table_id = f"{self.project_id}.{dataset_name}.conversations"
        try:
            schema = [
                bigquery.SchemaField("conversation_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("generated_sql", "STRING"),
                bigquery.SchemaField("query_id", "STRING"),
            ]
            table = bigquery.Table(table_id, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="timestamp")
            self.client.create_table(table)
            logger.info(f"테이블 생성 완료: {table_id}")
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
        """사용자의 대화 히스토리 목록 조회"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            table_check_result = self._ensure_table_exists(dataset_name, 'conversations', self._create_conversations_table)
            if not table_check_result['success']:
                return {"success": True, "conversations": [], "count": 0}
            
            query = f"""
            SELECT 
                conversation_id,
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
            GROUP BY conversation_id
            ORDER BY start_time DESC
            LIMIT @limit OFFSET @offset
            """
            job_config = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("offset", "INT64", offset)
            ])
            
            results = self.client.query(query, job_config=job_config).result()
            
            conversations = [{
                "conversation_id": row.conversation_id,
                "start_time": row.start_time.isoformat() if row.start_time else None,
                "last_time": row.last_time.isoformat() if row.last_time else None,
                "message_count": row.message_count,
                "first_message": row.first_message or "대화 없음"
            } for row in results]
            
            return {"success": True, "conversations": conversations, "count": len(conversations)}
        except Exception as e:
            logger.error(f"대화 히스토리 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "conversations": []}
