"""
BigQuery 유틸리티 클래스
Google Cloud BigQuery와의 연동을 담당
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, BadRequest, Forbidden

logger = logging.getLogger(__name__)

class BigQueryClient:
    """BigQuery 클라이언트 래퍼 클래스"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        BigQuery 클라이언트 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        try:
            self.client = bigquery.Client(project=project_id, location=location)
            logger.info(f"BigQuery 클라이언트 초기화 완료: {project_id} (리전: {location})")
        except Exception as e:
            logger.error(f"BigQuery 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def execute_query(self, sql_query: str, max_results: int = 1000) -> Dict[str, Any]:
        """
        BigQuery에서 SQL 쿼리 실행
        
        Args:
            sql_query: 실행할 SQL 쿼리
            max_results: 최대 결과 행 수
            
        Returns:
            실행 결과 딕셔너리
        """
        try:
            logger.info(f"쿼리 실행 시작: {sql_query[:100]}...")
            
            # 쿼리 작업 설정
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=10**10,  # 10GB 제한
                use_query_cache=True
            )
            
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # 결과 대기 (타임아웃 30초)
            results = query_job.result(timeout=30, max_results=max_results)
            
            # 결과를 딕셔너리 리스트로 변환
            rows = []
            for row in results:
                row_dict = {}
                for key, value in zip(row.keys(), row.values()):
                    # 날짜/시간 객체를 문자열로 변환
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                    elif hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                    else:
                        row_dict[key] = value
                rows.append(row_dict)
            
            # 쿼리 통계 수집
            stats = self._extract_job_stats(query_job)
            
            logger.info(f"쿼리 실행 완료: {len(rows)}행 반환")
            
            return {
                "success": True,
                "data": rows,
                "row_count": len(rows),
                "stats": stats
            }
            
        except BadRequest as e:
            logger.error(f"잘못된 쿼리: {str(e)}")
            return {
                "success": False,
                "error": f"SQL 문법 오류: {str(e)}",
                "error_type": "syntax_error"
            }
            
        except Forbidden as e:
            logger.error(f"권한 오류: {str(e)}")
            return {
                "success": False,
                "error": f"접근 권한이 없습니다: {str(e)}",
                "error_type": "permission_error"
            }
            
        except NotFound as e:
            logger.error(f"리소스 없음: {str(e)}")
            return {
                "success": False,
                "error": f"테이블 또는 데이터셋을 찾을 수 없습니다: {str(e)}",
                "error_type": "not_found"
            }
            
        except Exception as e:
            logger.error(f"쿼리 실행 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"쿼리 실행 실패: {str(e)}",
                "error_type": "execution_error"
            }
    
    def validate_query(self, sql_query: str) -> Dict[str, Any]:
        """
        SQL 쿼리 문법 검증 (실행하지 않음)
        
        Args:
            sql_query: 검증할 SQL 쿼리
            
        Returns:
            검증 결과
        """
        try:
            # 드라이 런으로 쿼리 검증
            job_config = bigquery.QueryJobConfig(
                dry_run=True,
                use_query_cache=False
            )
            
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # 예상 비용 계산 (TB당 $5 기준)
            bytes_processed = query_job.total_bytes_processed or 0
            tb_processed = bytes_processed / (1024**4)
            estimated_cost = tb_processed * 5
            
            return {
                "success": True,
                "valid": True,
                "bytes_processed": bytes_processed,
                "tb_processed": round(tb_processed, 6),
                "estimated_cost_usd": round(estimated_cost, 4),
                "message": "쿼리가 유효합니다"
            }
            
        except BadRequest as e:
            return {
                "success": True,
                "valid": False,
                "error": str(e),
                "message": "쿼리에 문법 오류가 있습니다"
            }
            
        except Exception as e:
            logger.error(f"쿼리 검증 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"검증 중 오류 발생: {str(e)}"
            }
    
    def list_datasets(self) -> Dict[str, Any]:
        """
        프로젝트의 데이터셋 목록 조회
        
        Returns:
            데이터셋 목록
        """
        try:
            datasets = list(self.client.list_datasets())
            
            dataset_list = []
            for dataset in datasets:
                dataset_info = {
                    "dataset_id": dataset.dataset_id,
                    "full_dataset_id": f"{self.project_id}.{dataset.dataset_id}",
                    "description": dataset.description or "",
                    "location": dataset.location or "US"
                }
                dataset_list.append(dataset_info)
            
            return {
                "success": True,
                "datasets": dataset_list,
                "count": len(dataset_list)
            }
            
        except Exception as e:
            logger.error(f"데이터셋 목록 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "datasets": []
            }
    
    def list_tables(self, dataset_id: str) -> Dict[str, Any]:
        """
        데이터셋의 테이블 목록 조회
        
        Args:
            dataset_id: 데이터셋 ID
            
        Returns:
            테이블 목록
        """
        try:
            dataset_ref = self.client.dataset(dataset_id)
            tables = list(self.client.list_tables(dataset_ref))
            
            table_list = []
            for table in tables:
                table_info = {
                    "table_id": table.table_id,
                    "full_table_id": f"{self.project_id}.{dataset_id}.{table.table_id}",
                    "table_type": table.table_type,
                    "created": table.created.isoformat() if table.created else None
                }
                table_list.append(table_info)
            
            return {
                "success": True,
                "tables": table_list,
                "count": len(table_list)
            }
            
        except NotFound:
            return {
                "success": False,
                "error": f"데이터셋 '{dataset_id}'를 찾을 수 없습니다",
                "tables": []
            }
            
        except Exception as e:
            logger.error(f"테이블 목록 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tables": []
            }
    
    def get_table_schema(self, dataset_id: str, table_id: str) -> Dict[str, Any]:
        """
        테이블 스키마 정보 조회
        
        Args:
            dataset_id: 데이터셋 ID
            table_id: 테이블 ID
            
        Returns:
            스키마 정보
        """
        try:
            table_ref = self.client.dataset(dataset_id).table(table_id)
            table = self.client.get_table(table_ref)
            
            schema_fields = []
            for field in table.schema:
                field_info = {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                }
                schema_fields.append(field_info)
            
            return {
                "success": True,
                "table_id": f"{self.project_id}.{dataset_id}.{table_id}",
                "schema": schema_fields,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None
            }
            
        except NotFound:
            return {
                "success": False,
                "error": f"테이블 '{dataset_id}.{table_id}'를 찾을 수 없습니다"
            }
            
        except Exception as e:
            logger.error(f"스키마 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def save_conversation(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 내용을 BigQuery에 저장 (개선된 버전)
        
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
            required_fields = ['conversation_id', 'message_id', 'message', 'message_type']
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
    
    def _clean_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 데이터를 BigQuery 삽입을 위해 정리
        
        Args:
            data: 원본 대화 데이터
            
        Returns:
            정리된 데이터
        """
        # 기본값 설정
        clean_data = {
            'conversation_id': data.get('conversation_id', ''),
            'message_id': data.get('message_id', ''),
            'user_id': data.get('user_id'),
            'user_email': data.get('user_email'),
            'session_id': data.get('session_id'),
            'is_authenticated': bool(data.get('is_authenticated', False)),
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
    
    def get_usage_count(self, session_id: str, ip_address: str) -> Dict[str, Any]:
        """
        비인증 사용자의 일일 사용량 조회 (개선된 버전)
        
        Args:
            session_id: 세션 ID
            ip_address: IP 주소
            
        Returns:
            사용량 정보
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            
            # 테이블 존재 확인
            try:
                table_ref = self.client.dataset(dataset_name).table('usage_tracking')
                self.client.get_table(table_ref)
            except NotFound:
                logger.warning(f"⚠️ 사용량 추적 테이블이 존재하지 않습니다: {usage_table}")
                # 테이블이 없으면 기본값 반환
                return {
                    "success": True,
                    "daily_count": 0,
                    "remaining": 10,
                    "table_missing": True
                }
            
            query = f"""
            SELECT daily_count, last_request
            FROM `{usage_table}`
            WHERE session_id = @session_id 
              AND ip_address = @ip_address
              AND date_key = CURRENT_DATE()
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                    bigquery.ScalarQueryParameter("ip_address", "STRING", ip_address)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            daily_count = results[0].daily_count if results else 0
            daily_limit = int(os.getenv('DAILY_USAGE_LIMIT', '10'))
            
            return {
                "success": True,
                "daily_count": daily_count,
                "remaining": max(0, daily_limit - daily_count),
                "daily_limit": daily_limit,
                "last_request": results[0].last_request.isoformat() if results and results[0].last_request else None
            }
            
        except Exception as e:
            logger.error(f"사용량 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "daily_count": 0,
                "remaining": 10  # 오류 시 안전한 기본값
            }
    
    def update_usage_count(self, session_id: str, ip_address: str, user_agent: str = "") -> Dict[str, Any]:
        """
        비인증 사용자의 사용량 업데이트 (개선된 버전)
        
        Args:
            session_id: 세션 ID
            ip_address: IP 주소
            user_agent: 브라우저 정보
            
        Returns:
            업데이트 결과
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            usage_table = f"{self.project_id}.{dataset_name}.usage_tracking"
            
            # 테이블 존재 확인
            try:
                table_ref = self.client.dataset(dataset_name).table('usage_tracking')
                self.client.get_table(table_ref)
            except NotFound:
                logger.warning(f"⚠️ 사용량 추적 테이블이 존재하지 않습니다: {usage_table}")
                return {
                    "success": False,
                    "error": "사용량 추적 테이블이 존재하지 않습니다",
                    "table_missing": True
                }
            
            # User-Agent 길이 제한
            if len(user_agent) > 1000:
                user_agent = user_agent[:1000]
            
            # MERGE 문을 사용하여 업데이트 또는 삽입
            query = f"""
            MERGE `{usage_table}` T
            USING (
              SELECT 
                @session_id as session_id,
                @ip_address as ip_address,
                @user_agent as user_agent,
                CURRENT_DATE() as date_key,
                CURRENT_TIMESTAMP() as last_request
            ) S
            ON T.session_id = S.session_id 
              AND T.ip_address = S.ip_address 
              AND T.date_key = S.date_key
            WHEN MATCHED THEN
              UPDATE SET 
                daily_count = T.daily_count + 1,
                last_request = S.last_request,
                user_agent = S.user_agent
            WHEN NOT MATCHED THEN
              INSERT (session_id, ip_address, user_agent, daily_count, last_request, date_key)
              VALUES (S.session_id, S.ip_address, S.user_agent, 1, S.last_request, S.date_key)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                    bigquery.ScalarQueryParameter("ip_address", "STRING", ip_address),
                    bigquery.ScalarQueryParameter("user_agent", "STRING", user_agent)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            logger.info(f"사용량 업데이트 완료: {session_id} ({ip_address})")
            return {
                "success": True,
                "updated_count": 1
            }
            
        except Exception as e:
            logger.error(f"사용량 업데이트 중 오류: {str(e)}")
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
    
    def get_conversation_details(self, conversation_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        특정 대화의 상세 내역 조회
        
        Args:
            conversation_id: 대화 ID
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            대화 상세 내역
        """
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{self.project_id}.{dataset_name}.conversations"
            
            # 사용자 권한 확인을 위한 WHERE 절
            where_clause = "WHERE conversation_id = @conversation_id"
            parameters = [
                bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id)
            ]
            
            if user_id:
                where_clause += " AND user_id = @user_id"
                parameters.append(
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                )
            
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
            {where_clause}
            ORDER BY timestamp ASC
            """
            
            job_config = bigquery.QueryJobConfig(query_parameters=parameters)
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
    
    def _extract_job_stats(self, query_job) -> Dict[str, Any]:
        """쿼리 작업 통계 추출 (수정된 버전)"""
        try:
            return {
                "job_id": query_job.job_id,
                "bytes_processed": query_job.total_bytes_processed,
                "bytes_billed": query_job.total_bytes_billed,
                "slot_ms": getattr(query_job, 'slot_millis', None),
                "creation_time": query_job.created.isoformat() if hasattr(query_job, 'created') and query_job.created else None,
                "start_time": query_job.started.isoformat() if hasattr(query_job, 'started') and query_job.started else None,
                "end_time": query_job.ended.isoformat() if hasattr(query_job, 'ended') and query_job.ended else None,
                "cache_hit": getattr(query_job, 'cache_hit', False),
                "state": getattr(query_job, 'state', None)
            }
        except Exception as e:
            logger.warning(f"통계 추출 중 오류: {str(e)}")
            return {
                "job_id": getattr(query_job, 'job_id', 'unknown'),
                "error": str(e)
            }
    
    def get_default_table_metadata(self) -> dict:
        """기본 테이블의 메타데이터 조회"""
        default_table = "nlq-ex.test_dataset.events_20210131"
        
        try:
            table = self.client.get_table(default_table)
            
            # 기본 정보
            table_info = {
                "table_id": default_table,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "size_mb": round((table.num_bytes or 0) / (1024 * 1024), 2),
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
                "description": table.description or ""
            }
            
            # 스키마 정보
            schema = []
            for field in table.schema:
                schema.append({
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                })
            
            return {
                "success": True,
                "table_info": table_info,
                "schema": schema
            }
            
        except Exception as e:
            logger.error(f"기본 테이블 메타데이터 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "table_info": {"table_id": default_table},
                "schema": []
            }
    
    def format_bytes(self, bytes_count: int) -> str:
        """바이트 수를 읽기 쉬운 형태로 포맷"""
        if bytes_count == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(bytes_count)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
    def get_session_conversation_details(self, conversation_id: str, session_id: str) -> Dict[str, Any]:
        """
        세션 ID로 특정 대화 상세 조회 (비인증 사용자용)
        
        Args:
            conversation_id: 대화 ID
            session_id: 세션 ID (권한 확인용)
            
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
            AND session_id = @session_id
            AND is_authenticated = false
            ORDER BY timestamp ASC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
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
            
            logger.info(f"세션 대화 상세 조회 완료: {conversation_id} ({len(messages)}개 메시지)")
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": messages,
                "message_count": len(messages)
            }
            
        except Exception as e:
            logger.error(f"세션 대화 상세 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "messages": []
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
            
            # 세션 대화가 있는지 먼저 확인
            check_query = f"""
            SELECT COUNT(*) as count
            FROM `{conversations_table}`
            WHERE session_id = @session_id
                AND is_authenticated = false
            """
            
            check_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("session_id", "STRING", session_id)
                ]
            )
            
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
                is_authenticated = true,
                metadata = CONCAT(
                    IFNULL(metadata, '{{}}'),
                    ', "linked_from_session": "', @session_id, '"'
                )
            WHERE session_id = @session_id
                AND is_authenticated = false
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
            
        except Exception as e:
            logger.error(f"세션 대화 연결 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "updated_rows": 0
            }