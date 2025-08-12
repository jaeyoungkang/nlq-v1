"""
인증 관련 라우트
Google 로그인, JWT 토큰 관리 등 - 로그인 필수 버전
"""

import os
import logging
import datetime
from flask import Blueprint, request, jsonify, g
from utils.auth_utils import auth_manager, require_auth
from utils.error_utils import ErrorResponse

logger = logging.getLogger(__name__)

# 블루프린트 생성
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/google-login', methods=['POST'])
def google_login():
    """
    Google ID 토큰을 검증하고 JWT 토큰 발급 (화이트리스트 검증 포함)
    """
    try:
        if not request.json or 'id_token' not in request.json:
            return jsonify(ErrorResponse.validation_error("Google ID 토큰이 필요합니다")), 400
        
        id_token_str = request.json['id_token']
        session_id = request.json.get('session_id')  # 비인증 세션이 있다면 연결용
        
        # Google 토큰 검증 (화이트리스트 검증 포함)
        verification_result = auth_manager.verify_google_token(id_token_str)
        
        if not verification_result['success']:
            error_type = verification_result.get('error_type', 'auth_error')
            
            # 화이트리스트 관련 에러 처리
            if error_type == 'access_denied':
                reason = verification_result.get('reason', 'unknown')
                user_status = verification_result.get('user_status')
                
                # 상태별 맞춤 메시지
                if reason == 'not_whitelisted':
                    error_message = "접근이 허용되지 않은 계정입니다. 관리자에게 계정 등록을 요청하세요."
                elif reason == 'pending_approval':
                    error_message = "계정 승인이 대기 중입니다. 관리자 승인 후 이용 가능합니다."
                elif reason == 'account_disabled':
                    error_message = "계정이 비활성화되었습니다. 관리자에게 문의하세요."
                else:
                    error_message = verification_result.get('error', '접근이 거부되었습니다.')
                
                return jsonify({
                    "success": False,
                    "error": error_message,
                    "error_type": "access_denied",
                    "details": {
                        "reason": reason,
                        "user_status": user_status,
                        "support_message": "문의사항이 있으시면 관리자에게 연락하세요.",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }
                }), 403
            
            # 기타 인증 오류
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
        
        # 세션 대화 연결 처리 (비인증 세션이 있던 경우)
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
        
        logger.info(f"🔐 Google 로그인 성공 (화이트리스트 통과): {user_info['email']}")
        
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
            },
            "whitelist_verified": True
        }
        
        # 화이트리스트 데이터 추가
        whitelist_data = verification_result.get('whitelist_data', {})
        if whitelist_data:
            response_data["user"]["whitelist_info"] = {
                "created_at": whitelist_data.get('created_at'),
                "last_login": whitelist_data.get('last_login')
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
@require_auth
def verify_token():
    """
    JWT 토큰 유효성 검증 및 사용자 정보 반환
    """
    try:
        return jsonify({
            "success": True,
            "valid": True,
            "user": g.current_user,
            "authenticated": True
        })
        
    except Exception as e:
        logger.error(f"❌ 토큰 검증 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"토큰 검증 실패: {str(e)}")), 500