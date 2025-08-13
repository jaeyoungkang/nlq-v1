"""
BigQuery 대화 서비스
대화 저장/조회/삭제 - 로그인 필수 버전
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
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
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
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
            
            # 공통 헬퍼로 테이블 존재 확인 및 자동 생성
            table_check_result = self._ensure_conversation_table_exists(dataset_name)
            if not table_check_result['success']:
                return {
                    "success": False,
                    "error": table_check_result['error']
                }
            
            # 테이블 참조
            table = self.client.get_table(table_ref)
            
            # 세션 메타데이터 관리 (첫 메시지인 경우)
            session_result = self._manage_session_metadata(conversation_data, dataset_name)
            if not session_result['success']:
                logger.warning(f"⚠️ 세션 메타데이터 관리 실패: {session_result['error']}")
                # 세션 메타데이터 실패해도 대화는 저장 계속
            
            # 메시지 데이터 삽입 (스트리밍 삽입 사용)
            logger.debug(f"🔍 BigQuery 삽입 데이터: {clean_data}")
            errors = self.client.insert_rows_json(table, [clean_data])
            
            if errors:
                logger.error(f"대화 저장 실패 - 상세 오류: {errors}")
                # 첫 번째 오류의 상세 정보 추출
                first_error = errors[0] if errors else {}
                error_details = {
                    'index': first_error.get('index', 'N/A'),
                    'errors': first_error.get('errors', [])
                }
                logger.error(f"대화 저장 오류 상세: {error_details}")
                return {
                    "success": False,
                    "error": f"저장 중 오류 발생: {error_details}"
                }
            
            logger.info(f"💾 대화 저장 완료: {clean_data['conversation_id']} - {clean_data['message_type']} (경량화 버전)")
            return {
                "success": True,
                "message": "대화가 성공적으로 저장되었습니다 (경량화 버전)",
                "message_id": clean_data['message_id'],
                "optimized": True,
                "session_metadata": session_result.get('action', 'none')
            }
            
        except Exception as e:
            logger.error(f"대화 저장 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        인증된 사용자의 대화 히스토리 조회 (테이블 자동 생성 포함)
        
        Args:
            user_id: 사용자 ID
            limit: 최대 조회 개수
            offset: 오프셋
            
        Returns:
            대화 히스토리 목록
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 공통 헬퍼로 테이블 존재 확인 및 자동 생성
            table_check_result = self._ensure_conversation_table_exists(dataset_name)
            if not table_check_result['success']:
                # 테이블 생성 실패시 빈 목록 반환
                return {
                    "success": True,
                    "conversations": [],
                    "count": 0,
                    "message": f"테이블 생성 실패: {table_check_result['error']}"
                }
            
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
        특정 대화의 상세 내역 조회 (사용자 권한 확인 포함, 테이블 자동 생성 포함)
        
        Args:
            conversation_id: 대화 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            대화 상세 내역
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 공통 헬퍼로 테이블 존재 확인 및 자동 생성
            table_check_result = self._ensure_conversation_table_exists(dataset_name)
            if not table_check_result['success']:
                # 테이블 생성 실패시 빈 메시지 목록 반환
                return {
                    "success": True,
                    "conversation_id": conversation_id,
                    "messages": [],
                    "message_count": 0
                }
            
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
                message_data = {
                    "message_id": row.message_id,
                    "message": row.message,
                    "message_type": row.message_type,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "query_type": row.query_type,
                    "generated_sql": row.generated_sql,
                    "execution_time_ms": row.execution_time_ms
                }
                
                # assistant 메시지에 쿼리 결과가 있는 경우, 저장된 결과 조회
                if row.message_type == 'assistant' and row.query_type == 'query_request' and row.generated_sql:
                    query_result = self.get_query_result(row.message_id, user_id)
                    if query_result['success']:
                        message_data['query_result_data'] = query_result['result_data']
                        message_data['query_row_count'] = query_result['row_count']
                
                messages.append(message_data)
            
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
        사용자의 특정 대화 삭제 (테이블 자동 생성 포함)
        
        Args:
            conversation_id: 삭제할 대화 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            삭제 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 공통 헬퍼로 테이블 존재 확인 및 자동 생성
            table_check_result = self._ensure_conversation_table_exists(dataset_name)
            if not table_check_result['success']:
                # 테이블이 없으면 삭제할 대화도 없음
                return {
                    "success": False,
                    "error": "삭제할 대화를 찾을 수 없습니다 (테이블 없음)"
                }
            
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
        
    
    def _clean_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 데이터를 BigQuery 삽입을 위해 정리 (경량화 버전)
        
        Args:
            data: 원본 대화 데이터
            
        Returns:
            경량화된 정리된 데이터
        """
        # 경량화된 기본 필드만 포함
        clean_data = {
            'conversation_id': data.get('conversation_id', ''),
            'message_id': data.get('message_id', ''),
            'user_id': data.get('user_id'),  # 필수 필드
            'message': str(data.get('message', '')),
            'message_type': data.get('message_type', ''),
            'timestamp': data.get('timestamp'),
        }
        
        # 조건부 저장 필드들
        query_type = data.get('query_type')
        if query_type:
            clean_data['query_type'] = query_type
        
        # SQL은 query_request 타입이고 실제 SQL이 있는 경우만 저장
        generated_sql = data.get('generated_sql')
        if generated_sql and query_type == 'query_request':
            # SQL 길이 제한 (2KB로 축소)
            if len(generated_sql) > 2000:
                clean_data['generated_sql'] = generated_sql[:2000] + '...[truncated]'
            else:
                clean_data['generated_sql'] = generated_sql
        
        # execution_time_ms는 assistant 메시지이고 값이 있는 경우만 (정수로 변환)
        execution_time_ms = data.get('execution_time_ms')
        if execution_time_ms is not None and data.get('message_type') == 'assistant':
            try:
                # 부동소수점을 정수로 변환 (밀리초 단위)
                clean_data['execution_time_ms'] = int(round(float(execution_time_ms)))
            except (ValueError, TypeError):
                # 변환 실패시 None으로 설정 (필드 생략)
                logger.warning(f"⚠️ execution_time_ms 변환 실패: {execution_time_ms}")
                pass
        
        # timestamp 처리
        if not clean_data['timestamp']:
            clean_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # 메시지 길이 제한 (3KB로 축소)
        if len(clean_data['message']) > 3000:
            clean_data['message'] = clean_data['message'][:3000] + '...[truncated]'
        
        return clean_data
    
    def _prepare_session_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        세션 메타데이터 준비 (중복 데이터 분리)
        
        Args:
            data: 원본 대화 데이터
            
        Returns:
            세션 메타데이터
        """
        import hashlib
        
        # User-Agent 해시화 (저장 공간 절약)
        user_agent = data.get('user_agent', '')
        user_agent_hash = None
        if user_agent:
            user_agent_hash = hashlib.md5(user_agent.encode('utf-8')).hexdigest()
        
        session_data = {
            'conversation_id': data.get('conversation_id', ''),
            'user_id': data.get('user_id'),
            'user_email': data.get('user_email'),
            'ip_address': data.get('ip_address'),
            'user_agent_hash': user_agent_hash,
            'session_start': data.get('timestamp') or datetime.now(timezone.utc).isoformat(),
            'last_activity': data.get('timestamp') or datetime.now(timezone.utc).isoformat(),
            'message_count': 1
        }
        
        return session_data
    
    def _manage_session_metadata(self, data: Dict[str, Any], dataset_name: str) -> Dict[str, Any]:
        """
        세션 메타데이터 관리 (MERGE문을 사용한 UPSERT 방식)
        
        Args:
            data: 대화 데이터
            dataset_name: 데이터셋 이름
            
        Returns:
            세션 메타데이터 처리 결과
        """
        try:
            conversation_id = data.get('conversation_id')
            if not conversation_id:
                return {"success": False, "error": "conversation_id가 없습니다"}
            
            # session_metadata 테이블 존재 확인 및 생성
            try:
                metadata_table_ref = self.client.dataset(dataset_name).table('session_metadata')
                metadata_table = self.client.get_table(metadata_table_ref)
                logger.debug(f"📊 session_metadata 테이블 존재 확인")
            except NotFound:
                logger.info(f"🔧 session_metadata 테이블이 없습니다. 자동 생성을 시도합니다.")
                metadata_creation_result = self._create_session_metadata_table(dataset_name)
                if not metadata_creation_result['success']:
                    logger.warning(f"⚠️ session_metadata 테이블 생성 실패, conversations만 사용: {metadata_creation_result['error']}")
                    return {
                        "success": True,
                        "action": "skipped",
                        "reason": f"session_metadata 생성 실패: {metadata_creation_result['error']}"
                    }
                metadata_table = self.client.get_table(metadata_table_ref)
            
            # 세션 메타데이터 준비
            session_data = self._prepare_session_metadata(data)
            current_timestamp = datetime.now(timezone.utc)
            
            # MERGE문을 사용한 UPSERT (스트리밍 버퍼 문제 해결)
            merge_query = f"""
            MERGE `{self.project_id}.{dataset_name}.session_metadata` T
            USING (
                SELECT 
                    @conversation_id as conversation_id,
                    @user_id as user_id,
                    @user_email as user_email,
                    @ip_address as ip_address,
                    @user_agent_hash as user_agent_hash,
                    @session_start as session_start,
                    @last_activity as last_activity
            ) S
            ON T.conversation_id = S.conversation_id
            WHEN MATCHED THEN
                UPDATE SET 
                    last_activity = S.last_activity,
                    message_count = T.message_count + 1
            WHEN NOT MATCHED THEN
                INSERT (
                    conversation_id, user_id, user_email, ip_address, 
                    user_agent_hash, session_start, last_activity, message_count
                )
                VALUES (
                    S.conversation_id, S.user_id, S.user_email, S.ip_address,
                    S.user_agent_hash, S.session_start, S.last_activity, 1
                )
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", session_data['user_id']),
                    bigquery.ScalarQueryParameter("user_email", "STRING", session_data['user_email']),
                    bigquery.ScalarQueryParameter("ip_address", "STRING", session_data['ip_address']),
                    bigquery.ScalarQueryParameter("user_agent_hash", "STRING", session_data['user_agent_hash']),
                    bigquery.ScalarQueryParameter("session_start", "TIMESTAMP", 
                        datetime.fromisoformat(session_data['session_start'].replace('Z', '+00:00'))),
                    bigquery.ScalarQueryParameter("last_activity", "TIMESTAMP", current_timestamp)
                ]
            )
            
            merge_job = self.client.query(merge_query, job_config=job_config)
            merge_job.result()  # 완료 대기
            
            return {
                "success": True,
                "action": "merged",
                "note": "MERGE문을 사용한 UPSERT 완료"
            }
            
        except Exception as e:
            logger.error(f"❌ 세션 메타데이터 관리 중 오류: {str(e)}")
            return {
                "success": True,  # 세션 메타데이터 실패해도 대화 저장은 계속
                "action": "failed",
                "reason": f"세션 메타데이터 오류: {str(e)}"
            }
    
    # === 공통 헬퍼 메서드 ===
    
    def _ensure_conversation_table_exists(self, dataset_name: str) -> Dict[str, Any]:
        """
        conversations 테이블 존재 확인 및 자동 생성 (공통 헬퍼)
        
        Args:
            dataset_name: 데이터셋 이름
            
        Returns:
            테이블 확인/생성 결과
        """
        conversations_table = f"{self.project_id}.{dataset_name}.conversations"
        table_ref = self.client.dataset(dataset_name).table('conversations')
        
        try:
            self.client.get_table(table_ref)
            logger.debug(f"📋 테이블 {conversations_table} 존재 확인")
            return {"success": True, "action": "exists"}
            
        except NotFound:
            logger.info(f"🔧 테이블 {conversations_table}가 존재하지 않습니다. 자동 생성을 시도합니다.")
            table_creation_result = self._ensure_tables_exist(dataset_name)
            
            if table_creation_result['success']:
                logger.info(f"✅ 테이블 {conversations_table} 자동 생성 완료")
                return {"success": True, "action": "created"}
            else:
                logger.error(f"❌ 테이블 생성 실패: {table_creation_result['error']}")
                return {
                    "success": False, 
                    "error": f"테이블 생성 실패: {table_creation_result['error']}"
                }
        except Exception as e:
            logger.error(f"❌ 테이블 확인 중 예상치 못한 오류: {str(e)}")
            return {"success": False, "error": f"테이블 확인 오류: {str(e)}"}
    
    # === 테이블 자동 생성 및 관리 메서드들 ===
    
    def _ensure_tables_exist(self, dataset_name: str) -> Dict[str, Any]:
        """
        필요한 테이블들이 존재하는지 확인하고 없으면 생성
        
        Args:
            dataset_name: BigQuery 데이터셋 이름
            
        Returns:
            테이블 생성 결과
        """
        try:
            # 먼저 데이터셋 존재 확인 및 생성
            dataset_result = self._ensure_dataset_exists(dataset_name)
            if not dataset_result['success']:
                return dataset_result
            
            # conversations 테이블 생성
            conversations_result = self._create_conversations_table(dataset_name)
            if not conversations_result['success']:
                return conversations_result
                
            # session_metadata 테이블 생성  
            metadata_result = self._create_session_metadata_table(dataset_name)
            if not metadata_result['success']:
                return metadata_result
            
            # query_results 테이블 생성
            query_results_result = self._create_query_results_table(dataset_name)
            if not query_results_result['success']:
                return query_results_result
            
            logger.info(f"✅ 모든 필수 테이블 생성 완료: {dataset_name}")
            return {
                "success": True,
                "message": "모든 테이블이 생성되었습니다",
                "tables_created": ["conversations", "session_metadata", "query_results"]
            }
            
        except Exception as e:
            logger.error(f"❌ 테이블 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"테이블 생성 실패: {str(e)}"
            }
    
    def _ensure_dataset_exists(self, dataset_name: str) -> Dict[str, Any]:
        """데이터셋 존재 확인 및 생성"""
        try:
            dataset_ref = self.client.dataset(dataset_name)
            
            try:
                dataset = self.client.get_dataset(dataset_ref)
                logger.debug(f"📂 데이터셋 {dataset_name} 존재 확인")
                return {"success": True, "message": "데이터셋 존재함"}
            except NotFound:
                # 데이터셋 생성
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = f"AAA 대화 저장용 데이터셋 (자동 생성: {datetime.now(timezone.utc).isoformat()})"
                
                dataset = self.client.create_dataset(dataset, timeout=30)
                logger.info(f"📂 데이터셋 자동 생성: {dataset_name}")
                
                return {
                    "success": True, 
                    "message": f"데이터셋 {dataset_name} 생성 완료"
                }
                
        except Exception as e:
            logger.error(f"❌ 데이터셋 생성/확인 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"데이터셋 처리 실패: {str(e)}"
            }
    
    def _create_conversations_table(self, dataset_name: str) -> Dict[str, Any]:
        """최적화된 conversations 테이블 생성"""
        try:
            table_id = f"{self.project_id}.{dataset_name}.conversations"
            table_ref = self.client.dataset(dataset_name).table('conversations')
            
            # 최적화된 스키마 정의 (경량화 적용)
            schema = [
                bigquery.SchemaField("conversation_id", "STRING", mode="REQUIRED", description="대화 세션 ID"),
                bigquery.SchemaField("message_id", "STRING", mode="REQUIRED", description="메시지 고유 ID"), 
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED", description="사용자 ID"),
                bigquery.SchemaField("message", "STRING", mode="REQUIRED", description="메시지 내용 (최대 3KB)"),
                bigquery.SchemaField("message_type", "STRING", mode="REQUIRED", description="메시지 타입: user, assistant"),
                bigquery.SchemaField("query_type", "STRING", mode="NULLABLE", description="쿼리 분류: query_request, metadata_request 등"),
                bigquery.SchemaField("generated_sql", "STRING", mode="NULLABLE", description="생성된 SQL (최대 2KB)"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED", description="메시지 생성 시간"),
                bigquery.SchemaField("execution_time_ms", "INTEGER", mode="NULLABLE", description="실행 시간 (밀리초)"),
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            
            # 테이블 설정
            table.description = "AAA 대화 메시지 저장 (경량화 버전)"
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            
            # 테이블 생성
            table = self.client.create_table(table)
            logger.info(f"📋 conversations 테이블 생성 완료: {table_id}")
            
            return {
                "success": True,
                "message": f"conversations 테이블 생성 완료",
                "table_id": table_id
            }
            
        except Exception as e:
            logger.error(f"❌ conversations 테이블 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": f"conversations 테이블 생성 실패: {str(e)}"
            }
    
    def _create_session_metadata_table(self, dataset_name: str) -> Dict[str, Any]:
        """세션 메타데이터 테이블 생성 (중복 데이터 분리용)"""
        try:
            table_id = f"{self.project_id}.{dataset_name}.session_metadata"
            table_ref = self.client.dataset(dataset_name).table('session_metadata')
            
            schema = [
                bigquery.SchemaField("conversation_id", "STRING", mode="REQUIRED", description="대화 세션 ID"),
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED", description="사용자 ID"),
                bigquery.SchemaField("user_email", "STRING", mode="REQUIRED", description="사용자 이메일"),
                bigquery.SchemaField("ip_address", "STRING", mode="NULLABLE", description="클라이언트 IP 주소"),
                bigquery.SchemaField("user_agent_hash", "STRING", mode="NULLABLE", description="User-Agent 해시값"),
                bigquery.SchemaField("session_start", "TIMESTAMP", mode="REQUIRED", description="세션 시작 시간"),
                bigquery.SchemaField("last_activity", "TIMESTAMP", mode="REQUIRED", description="마지막 활동 시간"),
                bigquery.SchemaField("message_count", "INTEGER", mode="NULLABLE", description="세션 내 메시지 수"),
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            table.description = "AAA 세션별 메타데이터 (중복 데이터 분리)"
            
            # 테이블 생성
            table = self.client.create_table(table)
            logger.info(f"📊 session_metadata 테이블 생성 완료: {table_id}")
            
            return {
                "success": True,
                "message": f"session_metadata 테이블 생성 완료",
                "table_id": table_id
            }
            
        except Exception as e:
            logger.error(f"❌ session_metadata 테이블 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": f"session_metadata 테이블 생성 실패: {str(e)}"
            }
    
    def _create_query_results_table(self, dataset_name: str) -> Dict[str, Any]:
        """쿼리 결과 저장용 별도 테이블 생성"""
        try:
            table_id = f"{self.project_id}.{dataset_name}.query_results"
            table_ref = self.client.dataset(dataset_name).table('query_results')
            
            schema = [
                bigquery.SchemaField("result_id", "STRING", mode="REQUIRED", description="쿼리 결과 고유 ID"),
                bigquery.SchemaField("message_id", "STRING", mode="REQUIRED", description="연결된 메시지 ID"),
                bigquery.SchemaField("conversation_id", "STRING", mode="REQUIRED", description="대화 세션 ID"),
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED", description="사용자 ID"),
                bigquery.SchemaField("generated_sql", "STRING", mode="REQUIRED", description="실행된 SQL 쿼리"),
                bigquery.SchemaField("result_data", "JSON", mode="REQUIRED", description="쿼리 실행 결과 데이터"),
                bigquery.SchemaField("row_count", "INTEGER", mode="NULLABLE", description="결과 행 수"),
                bigquery.SchemaField("data_size_bytes", "INTEGER", mode="NULLABLE", description="결과 데이터 크기(바이트)"),
                bigquery.SchemaField("execution_time_ms", "INTEGER", mode="NULLABLE", description="쿼리 실행 시간(밀리초)"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="결과 저장 시간"),
                bigquery.SchemaField("expires_at", "TIMESTAMP", mode="NULLABLE", description="만료 시간 (30일 후)"),
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            table.description = "AAA 쿼리 실행 결과 저장 (대용량 결과 전용)"
            
            # 파티셔닝 설정 (created_at 기준)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="created_at"
            )
            
            # 테이블 생성
            table = self.client.create_table(table)
            logger.info(f"📊 query_results 테이블 생성 완료: {table_id}")
            
            return {
                "success": True,
                "message": f"query_results 테이블 생성 완료",
                "table_id": table_id
            }
            
        except Exception as e:
            logger.error(f"❌ query_results 테이블 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": f"query_results 테이블 생성 실패: {str(e)}"
            }
    
    def save_query_result(self, query_result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        쿼리 실행 결과를 별도 테이블에 저장
        
        Args:
            query_result_data: 쿼리 결과 데이터
            {
                'message_id': str,
                'conversation_id': str, 
                'user_id': str,
                'generated_sql': str,
                'result_data': List[Dict],
                'row_count': int,
                'execution_time_ms': int
            }
            
        Returns:
            저장 결과
        """
        try:
            import json
            import uuid
            from datetime import datetime, timezone, timedelta
            
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            
            # query_results 테이블 존재 확인 및 생성
            table_ref = self.client.dataset(dataset_name).table('query_results')
            try:
                table = self.client.get_table(table_ref)
                logger.debug(f"📊 query_results 테이블 존재 확인")
            except NotFound:
                logger.info(f"🔧 query_results 테이블이 없습니다. 자동 생성을 시도합니다.")
                creation_result = self._create_query_results_table(dataset_name)
                if not creation_result['success']:
                    return {
                        "success": False,
                        "error": f"query_results 테이블 생성 실패: {creation_result['error']}"
                    }
                table = self.client.get_table(table_ref)
            
            # 결과 데이터 최적화
            result_data = query_result_data.get('result_data', [])
            result_json = json.dumps(result_data, ensure_ascii=False)
            data_size_bytes = len(result_json.encode('utf-8'))
            
            # 저장할 데이터 준비
            current_time = datetime.now(timezone.utc)
            expires_time = current_time + timedelta(days=30)  # 30일 후 만료
            
            # execution_time_ms를 정수로 변환
            execution_time_ms = query_result_data.get('execution_time_ms')
            if execution_time_ms is not None:
                try:
                    execution_time_ms = int(round(float(execution_time_ms)))
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ query_results.execution_time_ms 변환 실패: {execution_time_ms}, None으로 저장")
                    execution_time_ms = None
            
            save_data = {
                'result_id': str(uuid.uuid4()),
                'message_id': query_result_data.get('message_id'),
                'conversation_id': query_result_data.get('conversation_id'),
                'user_id': query_result_data.get('user_id'),
                'generated_sql': query_result_data.get('generated_sql', ''),
                'result_data': result_json,  # JSON 문자열로 저장
                'row_count': query_result_data.get('row_count', 0),
                'data_size_bytes': data_size_bytes,
                'execution_time_ms': execution_time_ms,
                'created_at': current_time.isoformat(),
                'expires_at': expires_time.isoformat()
            }
            
            # 테이블에 삽입
            errors = self.client.insert_rows_json(table, [save_data])
            
            if errors:
                logger.error(f"쿼리 결과 저장 실패: {errors}")
                return {
                    "success": False,
                    "error": f"쿼리 결과 저장 실패: {errors[0] if errors else 'Unknown error'}"
                }
            
            logger.info(f"💾 쿼리 결과 저장 완료: {save_data['result_id']} ({data_size_bytes:,} bytes)")
            return {
                "success": True,
                "result_id": save_data['result_id'],
                "data_size_bytes": data_size_bytes,
                "row_count": save_data['row_count']
            }
            
        except Exception as e:
            logger.error(f"❌ 쿼리 결과 저장 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"쿼리 결과 저장 오류: {str(e)}"
            }
    
    def get_query_result(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        저장된 쿼리 결과 조회
        
        Args:
            message_id: 메시지 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            쿼리 결과 데이터
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_name = f"{self.project_id}.{dataset_name}.query_results"
            
            query = f"""
            SELECT 
                result_id,
                generated_sql,
                result_data,
                row_count,
                data_size_bytes,
                execution_time_ms,
                created_at
            FROM `{table_name}`
            WHERE message_id = @message_id 
              AND user_id = @user_id
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("message_id", "STRING", message_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if not results:
                return {
                    "success": False,
                    "error": "저장된 쿼리 결과를 찾을 수 없습니다"
                }
            
            row = results[0]
            result_data = row.result_data
            
            # JSON 문자열을 파이썬 객체로 파싱
            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ result_data JSON 파싱 실패: message_id={message_id}")
            
            return {
                "success": True,
                "result_id": row.result_id,
                "generated_sql": row.generated_sql,
                "result_data": result_data,
                "row_count": row.row_count,
                "data_size_bytes": row.data_size_bytes,
                "execution_time_ms": row.execution_time_ms,
                "created_at": row.created_at.isoformat() if row.created_at else None
            }
            
        except Exception as e:
            logger.error(f"❌ 쿼리 결과 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"쿼리 결과 조회 오류: {str(e)}"
            }
    
    def get_conversation_context(self, conversation_id: str, user_id: str, 
                               max_messages: int = 3) -> Dict[str, Any]:
        """
        LLM 컨텍스트용 대화 기록 조회 (최근 N개 메시지)
        
        Args:
            conversation_id: 대화 세션 ID
            user_id: 사용자 ID (권한 확인)
            max_messages: 최대 메시지 수 (기본 3개)
        
        Returns:
            LLM 호출용 대화 컨텍스트
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            query = f"""
            SELECT 
                message,
                message_type,
                timestamp,
                query_type,
                generated_sql,
                message_id
            FROM `{self.project_id}.{dataset_name}.conversations`
            WHERE conversation_id = @conversation_id 
              AND user_id = @user_id
            ORDER BY timestamp DESC
            LIMIT @max_messages
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                    bigquery.ScalarQueryParameter("max_messages", "INT64", max_messages)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            # 시간순으로 정렬 (최신이 마지막)
            messages = []
            for row in reversed(results):
                messages.append({
                    "role": "user" if row.message_type == "user" else "assistant",
                    "content": row.message,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "metadata": {
                        "query_type": row.query_type,
                        "generated_sql": row.generated_sql
                    }
                })
            
            logger.info(f"🔄 대화 컨텍스트 조회 완료: {conversation_id} ({len(messages)}개 메시지)")
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": messages,
                "context_length": len(messages)
            }
            
        except Exception as e:
            logger.error(f"❌ 대화 컨텍스트 조회 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "messages": []
            }
    
    def get_user_recent_context(self, user_id: str, max_messages: int = 5, 
                               exclude_conversation_id: str = None) -> Dict[str, Any]:
        """
        사용자 기반 최근 대화 기록 조회 (conversation_id와 무관하게)
        
        Args:
            user_id: 사용자 ID
            max_messages: 최대 메시지 수 (기본 5개)
            exclude_conversation_id: 제외할 대화 ID (현재 대화 제외용)
        
        Returns:
            LLM 호출용 대화 컨텍스트
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            
            # 현재 대화 제외 조건
            exclude_condition = ""
            query_params = [
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("max_messages", "INT64", max_messages)
            ]
            
            if exclude_conversation_id:
                exclude_condition = "AND conversation_id != @exclude_conversation_id"
                query_params.append(
                    bigquery.ScalarQueryParameter("exclude_conversation_id", "STRING", exclude_conversation_id)
                )
            
            query = f"""
            SELECT 
                message,
                message_type,
                timestamp,
                query_type,
                generated_sql,
                conversation_id,
                message_id
            FROM `{self.project_id}.{dataset_name}.conversations`
            WHERE user_id = @user_id
              {exclude_condition}
            ORDER BY timestamp DESC
            LIMIT @max_messages
            """
            
            job_config = bigquery.QueryJobConfig(query_parameters=query_params)
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            # 시간순으로 정렬 (최신이 마지막)
            messages = []
            for row in reversed(results):
                messages.append({
                    "role": "user" if row.message_type == "user" else "assistant",
                    "content": row.message,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "metadata": {
                        "query_type": row.query_type,
                        "generated_sql": row.generated_sql,
                        "conversation_id": row.conversation_id,
                        "message_id": row.message_id
                    }
                })
            
            logger.info(f"🔄 사용자 최근 컨텍스트 조회 완료: {user_id} ({len(messages)}개 메시지)")
            return {
                "success": True,
                "user_id": user_id,
                "messages": messages,
                "context_length": len(messages)
            }
            
        except Exception as e:
            logger.error(f"❌ 사용자 컨텍스트 조회 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "messages": []
            }
    
    def optimize_context_size(self, messages: List[Dict], max_tokens: int = 2000) -> List[Dict]:
        """
        토큰 제한에 맞춰 컨텍스트 최적화
        
        Args:
            messages: 원본 메시지 리스트
            max_tokens: 최대 토큰 수 (한글 기준 최적화: 기본 2000토큰)
        
        Returns:
            최적화된 메시지 리스트
        """
        try:
            # 한글 토큰 추정 최적화 (1토큰 ≈ 2-3글자, 안전하게 2.5 적용)
            total_chars = sum(len(msg['content']) for msg in messages)
            estimated_tokens = total_chars / 2.5  # 한글 특성 고려
            
            if estimated_tokens <= max_tokens:
                logger.debug(f"📊 컨텍스트 크기 적절: {estimated_tokens:.0f} 토큰 (제한: {max_tokens})")
                return messages
            
            # 최신 메시지부터 유지하면서 크기 조절
            optimized_messages = []
            current_chars = 0
            
            for message in reversed(messages):
                msg_chars = len(message['content'])
                if (current_chars + msg_chars) / 2.5 > max_tokens:
                    break
                optimized_messages.insert(0, message)
                current_chars += msg_chars
            
            optimized_tokens = current_chars / 2.5
            logger.info(f"📊 컨텍스트 최적화 완료: {len(messages)} → {len(optimized_messages)}개 메시지 ({estimated_tokens:.0f} → {optimized_tokens:.0f} 토큰)")
            
            return optimized_messages
            
        except Exception as e:
            logger.error(f"❌ 컨텍스트 최적화 오류: {str(e)}")
            return messages[:3]  # 실패시 최근 3개만 반환
    
    def get_table_schemas(self) -> Dict[str, Any]:
        """
        현재 테이블 스키마 정보 조회 (디버깅/모니터링용)
        
        Returns:
            테이블 스키마 정보
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            
            result = {
                "dataset": dataset_name,
                "tables": {}
            }
            
            # conversations 테이블 스키마
            try:
                conversations_table = self.client.get_table(f"{self.project_id}.{dataset_name}.conversations")
                result["tables"]["conversations"] = {
                    "exists": True,
                    "num_rows": conversations_table.num_rows,
                    "size_bytes": conversations_table.num_bytes,
                    "created": conversations_table.created.isoformat() if conversations_table.created else None,
                    "schema": [{"name": field.name, "type": field.field_type, "mode": field.mode} 
                             for field in conversations_table.schema]
                }
            except NotFound:
                result["tables"]["conversations"] = {"exists": False}
            
            # session_metadata 테이블 스키마
            try:
                metadata_table = self.client.get_table(f"{self.project_id}.{dataset_name}.session_metadata")
                result["tables"]["session_metadata"] = {
                    "exists": True,
                    "num_rows": metadata_table.num_rows,
                    "size_bytes": metadata_table.num_bytes,
                    "created": metadata_table.created.isoformat() if metadata_table.created else None,
                    "schema": [{"name": field.name, "type": field.field_type, "mode": field.mode} 
                             for field in metadata_table.schema]
                }
            except NotFound:
                result["tables"]["session_metadata"] = {"exists": False}
            
            return {
                "success": True,
                "schemas": result
            }
            
        except Exception as e:
            logger.error(f"❌ 테이블 스키마 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }