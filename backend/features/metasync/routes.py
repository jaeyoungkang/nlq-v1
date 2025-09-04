"""
MetaSync Routes - API 엔드포인트
메타데이터 캐시 관리를 위한 REST API
"""

from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any

from features.metasync.services import MetaSyncService
from features.metasync.models import CacheUpdateRequest
from utils.error_utils import ErrorResponse, SuccessResponse
from utils.decorators import require_auth
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# MetaSync API Blueprint
metasync_bp = Blueprint('metasync', __name__, url_prefix='/api/metasync')


@metasync_bp.route('/cache', methods=['GET'])
def get_cache():
    """
    현재 캐시 데이터 조회
    
    Returns:
        캐시 데이터 및 메타데이터
    """
    try:
        # MetaSyncService 의존성 주입
        metasync_service: MetaSyncService = getattr(current_app, 'metasync_service', None)
        if not metasync_service:
            return jsonify(ErrorResponse.internal_error("MetaSync service not available")), 500
        
        # 캐시 데이터 조회 (원본 JSON 문자열 그대로 반환 - 순서 보장)
        cache_raw = metasync_service.repository.get_cache_data_raw()
        
        # JSON 문자열을 그대로 반환 (원본 순서 보장)
        from flask import Response
        return Response(cache_raw, content_type='application/json')
        
    except Exception as e:
        logger.error(f"Failed to get cache: {str(e)}")
        return jsonify(ErrorResponse.internal_error("Failed to retrieve cache")), 500


@metasync_bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """캐시 상태 조회"""
    try:
        metasync_service = getattr(current_app, 'metasync_service', None)
        if not metasync_service:
            return jsonify({"error": "MetaSync service not available"}), 500
        
        cache_status = metasync_service.get_cache_status()
        return jsonify(cache_status.to_dict())
        
    except Exception as e:
        logger.error(f"Failed to get cache status: {str(e)}")
        return jsonify({"error": "Failed to retrieve cache status"}), 500


@metasync_bp.route('/cache/refresh', methods=['POST'])
def refresh_cache():
    """캐시 업데이트/갱신 (Cloud Function 대체)"""
    try:
        metasync_service = getattr(current_app, 'metasync_service', None)
        if not metasync_service:
            return jsonify({"error": "MetaSync service not available"}), 500
        
        # 간단한 파라미터만 처리
        request_data = request.get_json() or {}
        update_request = CacheUpdateRequest(
            force_refresh=request_data.get('force_refresh', True)
        )
        
        result = metasync_service.update_cache(update_request)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to refresh cache: {str(e)}")
        return jsonify({"error": "Failed to refresh cache"}), 500




@metasync_bp.route('/health', methods=['GET'])
def health_check():
    """MetaSync 서비스 헬스체크"""
    try:
        metasync_service = getattr(current_app, 'metasync_service', None)
        if not metasync_service:
            return jsonify({"status": "unhealthy", "error": "Service not initialized"}), 503
        
        try:
            cache_status = metasync_service.get_cache_status()
            cache_available = cache_status.exists
        except:
            cache_available = False
        
        return jsonify({
            "status": "healthy" if cache_available else "degraded",
            "cache_available": cache_available,
            "service": "available"
        })
        
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


