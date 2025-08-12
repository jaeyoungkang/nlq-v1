"""
BigQuery 사용자 화이트리스트 관리 서비스
화이트리스트 기반 접근 제어 구현
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)

class UserManagementService:
    """BigQuery 기반 사용자 화이트리스트 관리 서비스"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        """
        사용자 관리 서비스 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        self.project_id = project_id
        self.location = location
        self.dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
        self.table_name = f"{project_id}.{self.dataset_name}.users_whitelist"
        
        try:
            self.client = bigquery.Client(project=project_id, location=location)
            logger.info(f"✅ UserManagementService 초기화 완료: {project_id}")
        except Exception as e:
            logger.error(f"❌ UserManagementService 초기화 실패: {str(e)}")
            raise
    
    def ensure_whitelist_table_exists(self) -> Dict[str, Any]:
        """
        사용자 화이트리스트 테이블 존재 확인 및 자동 생성
        
        Returns:
            테이블 생성/확인 결과
        """
        try:
            # 데이터셋 존재 확인
            dataset_ref = self.client.dataset(self.dataset_name)
            try:
                self.client.get_dataset(dataset_ref)
                logger.debug(f"📂 데이터셋 {self.dataset_name} 존재 확인")
            except NotFound:
                # 데이터셋 생성
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "사용자 화이트리스트 및 대화 저장용 데이터셋"
                self.client.create_dataset(dataset)
                logger.info(f"📂 데이터셋 자동 생성: {self.dataset_name}")
            
            # 테이블 존재 확인
            table_ref = dataset_ref.table('users_whitelist')
            try:
                self.client.get_table(table_ref)
                logger.debug(f"📋 화이트리스트 테이블 존재 확인: {self.table_name}")
                return {"success": True, "action": "exists"}
            except NotFound:
                # 테이블 생성
                return self._create_whitelist_table()
                
        except Exception as e:
            logger.error(f"❌ 화이트리스트 테이블 확인 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"테이블 확인 실패: {str(e)}"
            }
    
    def _create_whitelist_table(self) -> Dict[str, Any]:
        """화이트리스트 테이블 생성"""
        try:
            table_ref = self.client.dataset(self.dataset_name).table('users_whitelist')
            
            # 테이블 스키마 정의
            schema = [
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED", 
                                    description="Google 사용자 ID"),
                bigquery.SchemaField("email", "STRING", mode="REQUIRED", 
                                    description="이메일 주소"),
                bigquery.SchemaField("status", "STRING", mode="REQUIRED", 
                                    description="사용자 상태: active, pending, disabled"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", 
                                    description="생성 시간"),
                bigquery.SchemaField("last_login", "TIMESTAMP", mode="NULLABLE", 
                                    description="마지막 로그인 시간"),
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            table.description = "사용자 화이트리스트 테이블 - 접근 권한 관리"
            
            # 테이블 생성
            table = self.client.create_table(table)
            logger.info(f"📋 화이트리스트 테이블 생성 완료: {self.table_name}")
            
            return {
                "success": True,
                "action": "created",
                "table_id": self.table_name
            }
            
        except Exception as e:
            logger.error(f"❌ 화이트리스트 테이블 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": f"테이블 생성 실패: {str(e)}"
            }
    
    def check_user_access(self, email: str, user_id: str = None) -> Dict[str, Any]:
        """
        사용자 접근 권한 확인
        
        Args:
            email: 사용자 이메일
            user_id: Google 사용자 ID (선택사항)
            
        Returns:
            접근 권한 확인 결과
        """
        try:
            # 테이블 존재 확인
            table_check = self.ensure_whitelist_table_exists()
            if not table_check['success']:
                return {
                    "success": False,
                    "allowed": False,
                    "error": table_check['error']
                }
            
            # 사용자 조회 쿼리
            query = f"""
            SELECT user_id, email, status, created_at, last_login
            FROM `{self.table_name}`
            WHERE email = @email
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("email", "STRING", email)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if not results:
                logger.warning(f"🚫 화이트리스트에 없는 사용자: {email}")
                return {
                    "success": True,
                    "allowed": False,
                    "reason": "not_whitelisted",
                    "message": "화이트리스트에 등록되지 않은 사용자입니다."
                }
            
            user_row = results[0]
            user_status = user_row.status
            
            # 상태별 접근 권한 확인
            if user_status == 'active':
                logger.info(f"✅ 화이트리스트 접근 허용: {email}")
                return {
                    "success": True,
                    "allowed": True,
                    "status": user_status,
                    "user_data": {
                        "user_id": user_row.user_id,
                        "email": user_row.email,
                        "created_at": user_row.created_at.isoformat() if user_row.created_at else None,
                        "last_login": user_row.last_login.isoformat() if user_row.last_login else None
                    }
                }
            elif user_status == 'pending':
                logger.warning(f"⏳ 승인 대기 중인 사용자: {email}")
                return {
                    "success": True,
                    "allowed": False,
                    "reason": "pending_approval",
                    "status": user_status,
                    "message": "계정 승인이 대기 중입니다. 관리자에게 문의하세요."
                }
            elif user_status == 'disabled':
                logger.warning(f"🚫 비활성화된 사용자: {email}")
                return {
                    "success": True,
                    "allowed": False,
                    "reason": "account_disabled",
                    "status": user_status,
                    "message": "계정이 비활성화되었습니다. 관리자에게 문의하세요."
                }
            else:
                logger.error(f"❓ 알 수 없는 사용자 상태: {email} - {user_status}")
                return {
                    "success": True,
                    "allowed": False,
                    "reason": "unknown_status",
                    "status": user_status,
                    "message": "계정 상태를 확인할 수 없습니다."
                }
                
        except Exception as e:
            logger.error(f"❌ 사용자 접근 권한 확인 중 오류: {str(e)}")
            return {
                "success": False,
                "allowed": False,
                "error": f"접근 권한 확인 실패: {str(e)}"
            }
    
    def update_last_login(self, email: str) -> Dict[str, Any]:
        """
        사용자의 마지막 로그인 시간 업데이트
        
        Args:
            email: 사용자 이메일
            
        Returns:
            업데이트 결과
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            query = f"""
            UPDATE `{self.table_name}`
            SET last_login = @current_time
            WHERE email = @email
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("email", "STRING", email),
                    bigquery.ScalarQueryParameter("current_time", "TIMESTAMP", current_time)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            if query_job.num_dml_affected_rows > 0:
                logger.debug(f"🕐 마지막 로그인 시간 업데이트: {email}")
                return {
                    "success": True,
                    "updated": True
                }
            else:
                logger.warning(f"⚠️ 로그인 시간 업데이트 실패 - 사용자 없음: {email}")
                return {
                    "success": True,
                    "updated": False,
                    "reason": "user_not_found"
                }
                
        except Exception as e:
            logger.error(f"❌ 마지막 로그인 시간 업데이트 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"로그인 시간 업데이트 실패: {str(e)}"
            }
    
    def get_user_stats(self) -> Dict[str, Any]:
        """
        사용자 통계 조회 (관리자용)
        
        Returns:
            사용자 통계 정보
        """
        try:
            # 테이블 존재 확인
            table_check = self.ensure_whitelist_table_exists()
            if not table_check['success']:
                return {
                    "success": False,
                    "error": table_check['error']
                }
            
            query = f"""
            SELECT 
                status,
                COUNT(*) as count,
                MAX(last_login) as last_activity
            FROM `{self.table_name}`
            GROUP BY status
            ORDER BY count DESC
            """
            
            query_job = self.client.query(query)
            results = list(query_job.result())
            
            stats = {
                "total_users": 0,
                "by_status": {},
                "last_activity": None
            }
            
            overall_last_activity = None
            
            for row in results:
                stats["by_status"][row.status] = row.count
                stats["total_users"] += row.count
                
                if row.last_activity:
                    if not overall_last_activity or row.last_activity > overall_last_activity:
                        overall_last_activity = row.last_activity
            
            if overall_last_activity:
                stats["last_activity"] = overall_last_activity.isoformat()
            
            logger.info(f"📊 사용자 통계 조회 완료: {stats['total_users']}명")
            
            return {
                "success": True,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"❌ 사용자 통계 조회 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"통계 조회 실패: {str(e)}"
            }
    
    def add_user(self, email: str, user_id: str, status: str = 'active') -> Dict[str, Any]:
        """
        새 사용자를 화이트리스트에 추가 (내부 사용용)
        
        Args:
            email: 사용자 이메일
            user_id: Google 사용자 ID
            status: 사용자 상태 (기본값: 'active')
            
        Returns:
            사용자 추가 결과
        """
        try:
            # 테이블 존재 확인
            table_check = self.ensure_whitelist_table_exists()
            if not table_check['success']:
                return {
                    "success": False,
                    "error": table_check['error']
                }
            
            current_time = datetime.now(timezone.utc)
            
            query = f"""
            INSERT INTO `{self.table_name}` (user_id, email, status, created_at)
            VALUES (@user_id, @email, @status, @created_at)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                    bigquery.ScalarQueryParameter("email", "STRING", email),
                    bigquery.ScalarQueryParameter("status", "STRING", status),
                    bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", current_time)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # 완료 대기
            
            logger.info(f"➕ 사용자 화이트리스트 추가: {email} ({status})")
            
            return {
                "success": True,
                "message": f"사용자 {email}이 화이트리스트에 추가되었습니다",
                "user_data": {
                    "email": email,
                    "user_id": user_id,
                    "status": status,
                    "created_at": current_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 사용자 추가 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"사용자 추가 실패: {str(e)}"
            }