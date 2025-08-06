"""
라우트 패키지 초기화
각 라우트 모듈에서 블루프린트를 가져와 등록
"""

from .auth_routes import auth_bp
from .chat_routes import chat_bp
from .system_routes import system_bp

__all__ = ['auth_bp', 'chat_bp', 'system_bp']

def register_routes(app):
    """
    Flask 앱에 모든 라우트 블루프린트 등록
    
    Args:
        app: Flask 애플리케이션 인스턴스
    """
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(system_bp)