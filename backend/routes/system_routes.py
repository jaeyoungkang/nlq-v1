"""
시스템 관련 라우트
헬스체크, 관리자 기능, 메인 페이지 등 - 로그인 필수 버전
"""

import os
import logging
import datetime
from flask import Blueprint, render_template, jsonify, g
from utils.auth_utils import require_auth

logger = logging.getLogger(__name__)

# 블루프린트 생성
system_bp = Blueprint('system', __name__)

class ErrorResponse:
    @staticmethod
    def create(error_message: str, error_type: str = "general", details: dict = None):
        return {
            "success": False,
            "error": error_message,
            "error_type": error_type,
            "details": details or {},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    
    @staticmethod
    def internal_error(message: str):
        return ErrorResponse.create(message, "internal_error")


@system_bp.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@system_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint (로그인 필수 버전)"""
    from flask import current_app
    
    # 클라이언트들 가져오기
    llm_client = getattr(current_app, 'llm_client', None)
    bigquery_client = getattr(current_app, 'bigquery_client', None)
    
    # 인증 매니저 가져오기
    from utils.auth_utils import auth_manager
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": "4.0.0-login-required",
        "services": {
            "llm": {
                "status": "available" if llm_client else "unavailable",
                "provider": os.getenv('LLM_PROVIDER', 'anthropic')
            },
            "bigquery": {
                "status": "available" if bigquery_client else "unavailable",
                "project": os.getenv('GOOGLE_CLOUD_PROJECT', 'N/A'),
            },
            "auth": {
                "status": "available" if auth_manager.google_client_id and auth_manager.jwt_secret else "unavailable",
                "google_auth": "configured" if auth_manager.google_client_id else "not_configured",
                "jwt": "configured" if auth_manager.jwt_secret else "not_configured"
            }
        },
        "features": {
            "login_required": True,
            "guest_access": False,
            "authenticated_conversation_storage": True,
            "session_to_user_linking": True,
            "unlimited_usage": True
        }
    }
    
    all_services_available = all(s["status"] == "available" for s in health_status["services"].values())
    if not all_services_available:
        health_status["status"] = "degraded"
        return jsonify(health_status), 503
    return jsonify(health_status)


@system_bp.route('/api/admin/stats', methods=['GET'])
@require_auth
def get_system_stats():
    """
    시스템 통계 조회 (관리자용) - 로그인 필수 버전
    """
    try:
        # 관리자 권한 확인 (선택사항 - 특정 이메일 도메인만 허용)
        user_email = g.current_user.get('email', '')
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not bigquery_client:
            return jsonify(ErrorResponse.create("BigQuery client is not initialized", "bigquery")), 500
        
        from utils.auth_utils import auth_manager
        stats = {}
        
        # 1. 대화 통계 조회 (인증된 사용자만)
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{bigquery_client.project_id}.{dataset_name}.conversations"
            
            # 테이블 존재 확인 (없으면 빈 통계 반환)
            from google.cloud.exceptions import NotFound
            try:
                bigquery_client.client.get_table(conversations_table.replace(':', '.'))
            except NotFound:
                logger.warning(f"⚠️ 통계 조회: 테이블 {conversations_table}이 존재하지 않습니다")
                stats['conversations'] = {
                    'total_messages_7d': 0,
                    'total_conversations_7d': 0,
                    'authenticated_users_7d': 0,
                    'user_messages_7d': 0,
                    'ai_responses_7d': 0,
                    'note': '테이블이 아직 생성되지 않았습니다'
                }
                # 통계 조회 건너뛰기
                return jsonify({
                    "success": True,
                    "stats": stats,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
            
            stats_query = f"""
            SELECT 
              COUNT(*) as total_messages,
              COUNT(DISTINCT conversation_id) as total_conversations,
              COUNT(DISTINCT user_id) as authenticated_users,
              COUNT(CASE WHEN message_type = 'user' THEN 1 END) as user_messages,
              COUNT(CASE WHEN message_type = 'assistant' THEN 1 END) as ai_responses
            FROM `{conversations_table}`
            WHERE DATE(timestamp) >= CURRENT_DATE() - 7
              AND user_id IS NOT NULL
            """
            
            query_job = bigquery_client.client.query(stats_query)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                stats['conversations'] = {
                    'total_messages_7d': row.total_messages,
                    'total_conversations_7d': row.total_conversations,
                    'authenticated_users_7d': row.authenticated_users,
                    'user_messages_7d': row.user_messages,
                    'ai_responses_7d': row.ai_responses
                }
        except Exception as e:
            logger.warning(f"대화 통계 조회 실패: {str(e)}")
            stats['conversations'] = {'error': str(e)}
        
        # 2. 시스템 상태
        stats['system'] = {
            'active_sessions': len(auth_manager.active_sessions),
            'llm_status': 'available' if getattr(current_app, 'llm_client', None) else 'unavailable',
            'bigquery_status': 'available' if bigquery_client else 'unavailable',
            'auth_status': 'available' if auth_manager.google_client_id and auth_manager.jwt_secret else 'unavailable'
        }
        
        # 3. 환경 설정
        stats['config'] = {
            'login_required': True,
            'guest_access_disabled': True,
            'conversation_dataset': os.getenv('CONVERSATION_DATASET', 'assistant'),
            'bigquery_project': bigquery_client.project_id if bigquery_client else 'N/A',
            'environment': os.getenv('FLASK_ENV', 'production')
        }
        
        logger.info(f"📊 시스템 통계 조회: {user_email}")
        
        return jsonify({
            "success": True,
            "stats": stats,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 시스템 통계 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"통계 조회 실패: {str(e)}")), 500


@system_bp.route('/conversation-schemas', methods=['GET'])
@require_auth
def get_conversation_schemas():
    """
    대화 테이블 스키마 정보 조회 (경량화 모니터링용)
    """
    try:
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        # 테이블 스키마 조회
        schemas_result = bigquery_client.get_conversation_table_schemas()
        
        if not schemas_result['success']:
            return jsonify(ErrorResponse.service_error(
                schemas_result['error'], "bigquery"
            )), 500
        
        logger.info(f"📊 테이블 스키마 조회: {g.current_user['email']}")
        
        return jsonify({
            "success": True,
            "schemas": schemas_result['schemas'],
            "optimization_info": {
                "version": "경량화 버전 v2.0",
                "optimizations": [
                    "중복 데이터 분리 (session_metadata)",
                    "조건부 필드 저장",
                    "메시지 길이 제한 (3KB)",
                    "SQL 길이 제한 (2KB)",
                    "User-Agent 해시화",
                    "일별 파티셔닝"
                ],
                "estimated_savings": "~70% 스토리지 절약"
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 테이블 스키마 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"스키마 조회 실패: {str(e)}")), 500