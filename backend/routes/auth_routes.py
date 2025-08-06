"""
인증 관련 라우트
Google 로그인, JWT 토큰 관리, 사용량 조회 등
"""

import os
import logging
import datetime
from flask import Blueprint, request, jsonify, g
from utils.auth_utils import auth_manager, require_auth, optional_auth

logger = logging.getLogger(__name__)

# 블루프린트 생성
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 설정 상수 (라우트 함수 내부로 이동)

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
    def validation_error(message: str):
        return ErrorResponse.create(message, "validation_error")
    
    @staticmethod
    def service_error(message: str, service: str):
        return ErrorResponse.create(message, "service_error", {"service": service})
    
    @staticmethod
    def internal_error(message: str):
        return ErrorResponse.create(message, "internal_error")


@auth_bp.route('/google-login', methods=['POST'])
def google_login():
    """
    Google ID 토큰을 검증하고 JWT 토큰 발급 (세션 대화 연결 포함)
    """
    try:
        if not request.json or 'id_token' not in request.json:
            return jsonify(ErrorResponse.validation_error("Google ID 토큰이 필요합니다")), 400
        
        id_token_str = request.json['id_token']
        session_id = request.json.get('session_id')
        
        # Google 토큰 검증
        verification_result = auth_manager.verify_google_token(id_token_str)
        
        if not verification_result['success']:
            return jsonify(ErrorResponse.service_error(
                verification_result['error'], "google_auth"
            )), 401
        
        # JWT 토큰 생성
        user_info = verification_result['user_info']
        token_result = auth_manager.generate_jwt_tokens(user_info)
        
        if not token_result['success']:
            return jsonify(ErrorResponse.service_error(
                token_result['error'], "jwt_generation"
            )), 500
        
        # 세션 대화 연결 처리
        session_link_result = None
        if session_id:
            from flask import current_app
            bigquery_client = getattr(current_app, 'bigquery_client', None)
            if bigquery_client:
                try:
                    session_link_result = bigquery_client.link_session_to_user(
                        session_id, 
                        user_info['user_id'], 
                        user_info['email']
                    )
                    logger.info(f"🔗 세션 연결 결과: {session_link_result}")
                except Exception as e:
                    logger.warning(f"⚠️ 세션 연결 중 오류 (로그인은 계속 진행): {str(e)}")
                    session_link_result = {
                        "success": False,
                        "error": str(e),
                        "updated_rows": 0
                    }
        
        logger.info(f"🔐 Google 로그인 성공: {user_info['email']}")
        
        response_data = {
            "success": True,
            "message": "로그인 성공",
            "access_token": token_result['access_token'],
            "refresh_token": token_result['refresh_token'],
            "expires_in": token_result['expires_in'],
            "user": {
                "user_id": user_info['user_id'],
                "email": user_info['email'],
                "name": user_info['name'],
                "picture": user_info['picture']
            }
        }
        
        # 세션 연결 정보 추가
        if session_link_result:
            response_data["session_link"] = {
                "success": session_link_result["success"],
                "updated_conversations": session_link_result.get("updated_rows", 0),
                "message": session_link_result.get("message", "")
            }
            
            if session_link_result.get("updated_rows", 0) > 0:
                response_data["message"] = f"로그인 성공! 이전 대화 {session_link_result['updated_rows']}개가 계정에 연결되었습니다."
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Google 로그인 처리 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"로그인 처리 실패: {str(e)}")), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    리프레시 토큰을 사용하여 새로운 액세스 토큰 발급
    """
    try:
        if not request.json or 'refresh_token' not in request.json:
            return jsonify(ErrorResponse.validation_error("리프레시 토큰이 필요합니다")), 400
        
        refresh_token_str = request.json['refresh_token']
        
        # 토큰 갱신
        refresh_result = auth_manager.refresh_access_token(refresh_token_str)
        
        if not refresh_result['success']:
            error_type = refresh_result.get('error_type', 'refresh_error')
            status_code = 401 if error_type in ['token_expired', 'invalid_token'] else 500
            
            return jsonify(ErrorResponse.service_error(
                refresh_result['error'], "token_refresh"
            )), status_code
        
        logger.info(f"🔄 토큰 갱신 성공: {refresh_result['user_info']['email']}")
        
        return jsonify({
            "success": True,
            "message": "토큰 갱신 성공",
            "access_token": refresh_result['access_token'],
            "expires_in": refresh_result['expires_in'],
            "user": refresh_result['user_info']
        })
        
    except Exception as e:
        logger.error(f"❌ 토큰 갱신 처리 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"토큰 갱신 실패: {str(e)}")), 500


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    사용자 로그아웃 (토큰 무효화)
    """
    try:
        user_id = g.current_user['user_id']
        
        # 사용자 세션 제거
        logout_result = auth_manager.logout_user(user_id)
        
        if not logout_result['success']:
            return jsonify(ErrorResponse.service_error(
                logout_result['error'], "logout"
            )), 500
        
        logger.info(f"👋 로그아웃 성공: {g.current_user['email']}")
        
        return jsonify({
            "success": True,
            "message": "성공적으로 로그아웃되었습니다"
        })
        
    except Exception as e:
        logger.error(f"❌ 로그아웃 처리 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"로그아웃 실패: {str(e)}")), 500


@auth_bp.route('/verify', methods=['GET'])
@optional_auth
def verify_token():
    """
    JWT 토큰 유효성 검증 및 사용자 정보 반환
    """
    try:
        if g.is_authenticated:
            return jsonify({
                "success": True,
                "valid": True,
                "user": g.current_user,
                "authenticated": True
            })
        else:
            # 비인증 사용자의 경우 사용량 정보 포함
            ip_address = request.remote_addr or 'unknown'
            user_agent = request.headers.get('User-Agent', '')
            session_id = auth_manager.generate_session_id(ip_address, user_agent)
            
            can_use, remaining = auth_manager.check_usage_limit(session_id)
            daily_usage_limit = int(os.getenv('DAILY_USAGE_LIMIT', '5'))
            
            return jsonify({
                "success": True,
                "valid": False,
                "authenticated": False,
                "usage": {
                    "daily_limit": daily_usage_limit,
                    "remaining": remaining,
                    "can_use": can_use
                }
            })
        
    except Exception as e:
        logger.error(f"❌ 토큰 검증 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"토큰 검증 실패: {str(e)}")), 500


@auth_bp.route('/usage', methods=['GET'])
@optional_auth
def get_usage():
    """
    현재 사용자의 사용량 정보 조회
    """
    try:
        daily_usage_limit = int(os.getenv('DAILY_USAGE_LIMIT', '5'))
        
        if g.is_authenticated:
            return jsonify({
                "success": True,
                "authenticated": True,
                "unlimited": True,
                "message": "인증된 사용자는 무제한 이용 가능합니다"
            })
        else:
            # 비인증 사용자의 사용량 조회
            ip_address = request.remote_addr or 'unknown'
            user_agent = request.headers.get('User-Agent', '')
            session_id = auth_manager.generate_session_id(ip_address, user_agent)
            
            can_use, remaining = auth_manager.check_usage_limit(session_id)
            
            return jsonify({
                "success": True,
                "authenticated": False,
                "usage": {
                    "daily_limit": daily_usage_limit,
                    "used": daily_usage_limit - remaining,
                    "remaining": remaining,
                    "can_use": can_use
                },
                "message": f"오늘 {remaining}회 더 이용 가능합니다" if can_use else "일일 사용 제한에 도달했습니다"
            })
        
    except Exception as e:
        logger.error(f"❌ 사용량 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"사용량 조회 실패: {str(e)}")), 500