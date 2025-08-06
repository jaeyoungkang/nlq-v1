"""
시스템 관련 라우트
헬스체크, 관리자 기능, 메인 페이지 등
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
    """Health check endpoint (업데이트됨)"""
    from flask import current_app
    
    # 클라이언트들 가져오기
    llm_client = getattr(current_app, 'llm_client', None)
    bigquery_client = getattr(current_app, 'bigquery_client', None)
    
    # 인증 매니저 가져오기
    from utils.auth_utils import auth_manager
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": "3.2.0-auth-only-restore",
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
            "guest_conversation_restore": False,
            "authenticated_conversation_restore": True,
            "session_to_user_linking": True,
            "conversation_storage": True
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
    시스템 통계 조회 (관리자용)
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
        
        # 1. 대화 통계 조회
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'assistant')
            conversations_table = f"{bigquery_client.project_id}.{dataset_name}.conversations"
            
            stats_query = f"""
            SELECT 
              COUNT(*) as total_messages,
              COUNT(DISTINCT conversation_id) as total_conversations,
              COUNT(DISTINCT user_id) as authenticated_users,
              COUNT(DISTINCT session_id) as guest_sessions,
              COUNT(CASE WHEN message_type = 'user' THEN 1 END) as user_messages,
              COUNT(CASE WHEN message_type = 'assistant' THEN 1 END) as ai_responses,
              COUNT(CASE WHEN is_authenticated = true THEN 1 END) as auth_messages,
              COUNT(CASE WHEN is_authenticated = false THEN 1 END) as guest_messages
            FROM `{conversations_table}`
            WHERE DATE(timestamp) >= CURRENT_DATE() - 7
            """
            
            query_job = bigquery_client.client.query(stats_query)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                stats['conversations'] = {
                    'total_messages_7d': row.total_messages,
                    'total_conversations_7d': row.total_conversations,
                    'authenticated_users_7d': row.authenticated_users,
                    'guest_sessions_7d': row.guest_sessions,
                    'user_messages_7d': row.user_messages,
                    'ai_responses_7d': row.ai_responses,
                    'auth_messages_7d': row.auth_messages,
                    'guest_messages_7d': row.guest_messages
                }
        except Exception as e:
            logger.warning(f"대화 통계 조회 실패: {str(e)}")
            stats['conversations'] = {'error': str(e)}
        
        # 2. 사용량 통계 조회
        try:
            usage_table = f"{bigquery_client.project_id}.{dataset_name}.usage_tracking"
            
            usage_query = f"""
            SELECT 
              COUNT(DISTINCT session_id) as unique_sessions_today,
              SUM(daily_count) as total_requests_today,
              AVG(daily_count) as avg_requests_per_session,
              MAX(daily_count) as max_requests_per_session
            FROM `{usage_table}`
            WHERE date_key = CURRENT_DATE()
            """
            
            query_job = bigquery_client.client.query(usage_query)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                stats['usage'] = {
                    'unique_sessions_today': row.unique_sessions_today,
                    'total_requests_today': row.total_requests_today,
                    'avg_requests_per_session': float(row.avg_requests_per_session) if row.avg_requests_per_session else 0,
                    'max_requests_per_session': row.max_requests_per_session
                }
        except Exception as e:
            logger.warning(f"사용량 통계 조회 실패: {str(e)}")
            stats['usage'] = {'error': str(e)}
        
        # 3. 시스템 상태
        stats['system'] = {
            'active_sessions': len(auth_manager.active_sessions),
            'memory_usage_counters': len(auth_manager.usage_counter),
            'llm_status': 'available' if getattr(current_app, 'llm_client', None) else 'unavailable',
            'bigquery_status': 'available' if bigquery_client else 'unavailable',
            'auth_status': 'available' if auth_manager.google_client_id and auth_manager.jwt_secret else 'unavailable'
        }
        
        # 4. 환경 설정
        daily_usage_limit = int(os.getenv('DAILY_USAGE_LIMIT', '5'))
        stats['config'] = {
            'daily_usage_limit': daily_usage_limit,
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