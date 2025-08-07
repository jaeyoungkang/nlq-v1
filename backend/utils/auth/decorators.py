"""
인증 데코레이터 모듈
Flask 라우트에 적용할 인증 관련 데코레이터들 - 로그인 필수만 지원
"""

import os
import logging
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

def require_auth(f):
    """
    인증이 필수인 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # AuthManager는 순환 import 방지를 위해 함수 내에서 import
        from . import auth_manager
        
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': '인증 토큰이 필요합니다',
                'error_type': 'missing_token'
            }), 401
        
        token = auth_header.split(' ')[1]
        verification_result = auth_manager.verify_jwt_token(token)
        
        if not verification_result['success']:
            return jsonify({
                'success': False,
                'error': verification_result['error'],
                'error_type': verification_result.get('error_type', 'auth_error')
            }), 401
        
        # 요청 컨텍스트에 사용자 정보 저장
        g.current_user = verification_result['user_info']
        g.is_authenticated = True
        
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """
    관리자 권한이 필요한 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 먼저 인증 확인
        if not getattr(g, 'is_authenticated', False):
            return jsonify({
                'success': False,
                'error': '인증이 필요합니다',
                'error_type': 'authentication_required'
            }), 401
        
        # 관리자 권한 확인 (환경변수로 관리자 이메일 도메인 설정)
        user_email = g.current_user.get('email', '')
        admin_domains = os.getenv('ADMIN_EMAIL_DOMAINS', '').split(',')
        admin_emails = os.getenv('ADMIN_EMAILS', '').split(',')
        
        is_admin = False
        
        # 도메인 기반 확인
        if admin_domains and admin_domains[0]:  # 빈 문자열이 아닌 경우
            is_admin = any(user_email.endswith(domain.strip()) for domain in admin_domains if domain.strip())
        
        # 특정 이메일 기반 확인
        if not is_admin and admin_emails and admin_emails[0]:  # 빈 문자열이 아닌 경우
            is_admin = user_email in [email.strip() for email in admin_emails if email.strip()]
        
        # 환경변수가 설정되지 않은 경우 모든 인증된 사용자를 관리자로 처리 (개발용)
        if not admin_domains[0] and not admin_emails[0]:
            logger.warning("⚠️ 관리자 설정이 없습니다. 모든 인증된 사용자를 관리자로 처리합니다.")
            is_admin = True
        
        if not is_admin:
            return jsonify({
                'success': False,
                'error': '관리자 권한이 필요합니다',
                'error_type': 'insufficient_permissions'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function