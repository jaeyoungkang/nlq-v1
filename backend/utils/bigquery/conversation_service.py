"""
BigQuery 대화 서비스
대화 저장/조회/삭제 - 로그인 필수 버전
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)

class ConversationService:
    """BigQuery 대화 관리 서비스 - 로그인 필수 버전"""
    
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
        """
        대화 내용을 BigQuery에 저장 (로그인 사용자 전용)
        
        Args:
            conversation_data: 저장할 대화 데이터
            
        Returns:
            저장 결과
        """
        try:
            # 대화 테이블 설정 (환경에 맞게 수정)
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            
            # 필수 필드 검증
            required_fields = ['conversation_id', 'message_id', 'message', 'message_type', 'user_id']
            for field in required_fields:
                if field not in conversation_data:
                    raise ValueError(f"필수 필드 누락: {field}")
            
            # 데이터 타입 검증 및 정리
            clean_data = self._clean_conversation_data(conversation_data)
            
            # BigQuery 테이블 참조
            table_ref = self.client.dataset(dataset_name).table('conversations')
            
            # 테이블 존재 확인 및 생성
            try:
                table = self.client.get_table(table_ref)
            except NotFound:
                logger.warning(f"⚠️ 테이블 {table_id}가 존재하지 않습니다. 수동으로 생성해주세요.")
                return {
                    "success": False,
                    "error": f"테이블 {table_id}가 존재하지 않습니다. BigQuery에서 테이블을 먼저 생성해주세요."
                }
            
            # 데이터 삽입 (스트리밍 삽입 사용)
            errors = self.client.insert_rows_json(table, [clean_data])
            
            if errors:
                logger.error(f"대화 저장 실패: {errors}")
                return {
                    "success": False,
                    "error": f"저장 중 오류 발생: {errors[0] if errors else 'Unknown error'}"
                }
            
            logger.info(f"대화 저장 완료: {clean_data['conversation_id']} - {clean_data['message_type']}")
            return {
                "success": True,
                "message": "대화가 성공적으로 저장되었습니다",
                "message_id": clean_data['message_id']
            }
            
        except Exception as e:
            logger.error(f"대화 저장 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        인증된 사용자의 대화 히스토리 조회
        
        Args:
            user_id: 사용자 ID
            limit: 최대 조회 개수
            offset: 오프셋
            
        Returns:
            대화 히스토리 목록
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            query = f"""
            SELECT 
                conversation_id,
                MIN(timestamp) as start_time,
                MAX(timestamp) as last_time,
                COUNT(*) as message_count,
                STRING_AGG(
                    CASE WHEN message_type = 'user' THEN message END, 
                    ' | ' 
                    ORDER BY timestamp 
                    LIMIT 1
                ) as first_message
            FROM `{conversations_table}`
            WHERE user_id = @user_id
            GROUP BY conversation_id
            ORDER BY start_time DESC
            LIMIT @limit OFFSET @offset
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),
                    bigquery.ScalarQueryParameter("offset", "INT64", offset)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            conversations = []
            for row in results:
                conversations.append({
                    "conversation_id": row.conversation_id,
                    "start_time": row.start_time.isoformat() if row.start_time else None,
                    "last_time": row.last_time.isoformat() if row.last_time else None,
                    "message_count": row.message_count,
                    "first_message": row.first_message or "대화 없음"
                })
            
            return {
                "success": True,
                "conversations": conversations,
                "count": len(conversations)
            }
            
        except Exception as e:
            logger.error(f"대화 히스토리 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "conversations": []
            }
    
    def get_conversation_details(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        특정 대화의 상세 내역 조회 (사용자 권한 확인 포함)
        
        Args:
            conversation_id: 대화 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            대화 상세 내역
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            query = f"""
            SELECT 
                message_id,
                message,
                message_type,
                timestamp,
                query_type,
                generated_sql,
                execution_time_ms
            FROM `{conversations_table}`
            WHERE conversation_id = @conversation_id 
              AND user_id = @user_id
            ORDER BY timestamp ASC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            messages = []
            for row in results:
                messages.append({
                    "message_id": row.message_id,
                    "message": row.message,
                    "message_type": row.message_type,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "query_type": row.query_type,
                    "generated_sql": row.generated_sql,
                    "execution_time_ms": row.execution_time_ms
                })
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": messages,
                "message_count": len(messages)
            }
            
        except Exception as e:
            logger.error(f"대화 상세 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "messages": []
            }
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        사용자의 특정 대화 삭제
        
        Args:
            conversation_id: 삭제할 대화 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            삭제 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            query = f"""
            DELETE FROM `{conversations_table}`
            WHERE conversation_id = @conversation_id 
              AND user_id = @user_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            # 삭제된 행 수 확인
            if query_job.num_dml_affected_rows > 0:
                logger.info(f"대화 삭제 완료: {conversation_id} (사용자: {user_id})")
                return {
                    "success": True,
                    "message": f"대화 {conversation_id}가 성공적으로 삭제되었습니다",
                    "deleted_rows": query_job.num_dml_affected_rows
                }
            else:
                return {
                    "success": False,
                    "error": "삭제할 대화를 찾을 수 없습니다"
                }
            
        except Exception as e:
            logger.error(f"대화 삭제 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        
    def link_session_to_user(self, session_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """
        세션 ID의 모든 대화를 사용자 계정으로 연결 (로그인 시 사용)
        
        Args:
            session_id: 연결할 세션 ID
            user_id: 사용자 ID
            user_email: 사용자 이메일
            
        Returns:
            연결 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 세션 대화가 있는지 먼저 확인 (session_id 컬럼이 존재하는 경우)
            check_query = f"""
            SELECT COUNT(*) as count
            FROM `{conversations_table}`
            WHERE session_id = @session_id
                AND (user_id IS NULL OR user_id = '')
            """
            
            check_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
                ]
            )
            
            try:
                check_job = self.client.query(check_query, job_config=check_job_config)
                check_result = list(check_job.result())
                
                if not check_result or check_result[0].count == 0:
                    logger.info(f"세션 {session_id}에 연결할 대화가 없습니다")
                    return {
                        "success": True,
                        "message": "연결할 세션 대화가 없습니다",
                        "updated_rows": 0
                    }
                
                # 세션의 모든 대화를 사용자 계정으로 업데이트
                update_query = f"""
                UPDATE `{conversations_table}`
                SET 
                    user_id = @user_id,
                    user_email = @user_email,
                    metadata = CONCAT(
                        IFNULL(metadata, '{{}}'),
                        ', "linked_from_session": "', @session_id, '"'
                    )
                WHERE session_id = @session_id
                    AND (user_id IS NULL OR user_id = '')
                """
                
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                        bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                        bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                    ]
                )
                
                query_job = self.client.query(update_query, job_config=job_config)
                query_job.result()  # 완료 대기
                
                updated_rows = query_job.num_dml_affected_rows or 0
                
                logger.info(f"세션 대화 연결 완료: {session_id} -> {user_email} ({updated_rows}행 업데이트)")
                
                return {
                    "success": True,
                    "message": f"세션 대화 {updated_rows}개가 사용자 계정으로 연결되었습니다",
                    "updated_rows": updated_rows,
                    "session_id": session_id,
                    "user_id": user_id
                }
                
            except Exception as query_error:
                # session_id 컬럼이 없거나 다른 스키마 오류인 경우
                logger.warning(f"세션 연결 쿼리 실패 (스키마 변경 필요할 수 있음): {str(query_error)}")
                return {
                    "success": True,
                    "message": "세션 연결 기능을 사용할 수 없습니다 (테이블 스키마 확인 필요)",
                    "updated_rows": 0,
                    "warning": str(query_error)
                }
            
        except Exception as e:
            logger.error(f"세션 대화 연결 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "updated_rows": 0
            }
    
    def _clean_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 데이터를 BigQuery 삽입을 위해 정리 (로그인 필수 버전)
        
        Args:
            data: 원본 대화 데이터
            
        Returns:
            정리된 데이터
        """
        # 기본값 설정 (로그인 사용자 전용)
        clean_data = {
            'conversation_id': data.get('conversation_id', ''),
            'message_id': data.get('message_id', ''),
            'user_id': data.get('user_id'),  # 필수 필드
            'user_email': data.get('user_email'),  # 필수 필드
            'message': str(data.get('message', '')),
            'message_type': data.get('message_type', ''),
            'query_type': data.get('query_type'),
            'generated_sql': data.get('generated_sql'),
            'timestamp': data.get('timestamp'),
            'ip_address': data.get('ip_address', 'unknown'),
            'user_agent': data.get('user_agent', ''),
            'execution_time_ms': data.get('execution_time_ms'),
            'metadata': data.get('metadata', {})
        }
        
        # timestamp 처리
        if not clean_data['timestamp']:
            clean_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # 메시지 길이 제한 (BigQuery STRING 필드 제한 고려)
        if len(clean_data['message']) > 10000:  # 10KB 제한
            clean_data['message'] = clean_data['message'][:10000] + '...[truncated]'
        
        # SQL 길이 제한
        if clean_data['generated_sql'] and len(clean_data['generated_sql']) > 5000:
            clean_data['generated_sql'] = clean_data['generated_sql'][:5000] + '...[truncated]'
        
        # User-Agent 길이 제한
        if len(clean_data['user_agent']) > 1000:
            clean_data['user_agent'] = clean_data['user_agent'][:1000]
        
        # JSON 메타데이터 직렬화
        if isinstance(clean_data['metadata'], dict):
            # 안전한 JSON 직렬화
            try:
                clean_data['metadata'] = json.dumps(clean_data['metadata'], ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                clean_data['metadata'] = '{}'
        elif clean_data['metadata'] is None:
            clean_data['metadata'] = '{}'
        else:
            # 이미 문자열인 경우 그대로 사용
            clean_data['metadata'] = str(clean_data['metadata'])
        
        return clean_data