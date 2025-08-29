"""
시스템 관련 라우트
헬스체크, 관리자 기능, 메인 페이지 등 - 로그인 필수 버전
"""

import os
import logging
import datetime
from flask import Blueprint, render_template, jsonify, g
from utils.auth_utils import require_auth
from utils.error_utils import ErrorResponse

logger = logging.getLogger(__name__)

# 블루프린트 생성
system_bp = Blueprint('system', __name__)


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