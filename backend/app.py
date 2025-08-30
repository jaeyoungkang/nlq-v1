import os
import json
import logging
import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

# Import utility modules
from utils.llm_client import LLMClientFactory
from utils.logging_utils import get_logger
from utils.error_utils import ErrorResponse
from utils.token_utils import TokenHandler
from features.authentication.repositories import AuthRepository
from features.authentication.services import AuthService

# Import route blueprints directly from features
from features.authentication.routes import auth_bp
from features.chat.routes import chat_bp
from features.system.routes import system_bp

# Import new repositories
from features.system.repositories import SystemRepository
from features.query_processing.repositories import QueryProcessingRepository
from features.chat.repositories import ChatRepository

# Import services
from features.chat.services import ChatService
from features.input_classification.services import InputClassificationService
from features.query_processing.services import QueryProcessingService
from features.data_analysis.services import AnalysisService

# --- Configuration and Logging ---

# Load environment variables from .env.local
import pathlib
env_path = pathlib.Path(__file__).parent / '.env.local'
load_dotenv(env_path)

# Improved logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = get_logger(__name__)

# Initialize Flask web application
app = Flask(__name__)

# --- CORS Configuration ---
# Allow requests from the Next.js development server and production domains
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, origins=allowed_origins, supports_credentials=True)

# --- Global Client Initialization ---

def initialize_services():
    """Initialize core services and application dependencies"""
    
    try:
        # Initialize LLM client (애플리케이션 공통 서비스)
        llm_provider = os.getenv('LLM_PROVIDER', 'anthropic')
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if api_key:
            app.llm_client = LLMClientFactory.create_client(llm_provider, {'api_key': api_key})
            logger.success(f"{llm_provider} LLM client initialized successfully")
        else:
            logger.warning("ANTHROPIC_API_KEY is not set")
        
        # Initialize Auth (라우팅에 필요한 횡단 관심사)
        try:
            google_client_id = os.getenv('GOOGLE_CLIENT_ID')
            jwt_secret = os.getenv('JWT_SECRET_KEY')
            
            if google_client_id and jwt_secret:
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
                location = os.getenv('BIGQUERY_LOCATION', 'asia-northeast3')
                
                app.token_handler = TokenHandler(google_client_id, jwt_secret)
                app.auth_repository = AuthRepository(project_id, location)
                app.auth_service = AuthService(app.token_handler, app.auth_repository)
                
                logger.success("Auth services initialized successfully")
            else:
                logger.warning("Google Client ID 또는 JWT Secret이 설정되지 않았습니다")
        except Exception as e:
            logger.error(f"Auth services initialization failed: {str(e)}")
        
        # Initialize feature repositories (각 feature가 자체 BigQuery 클라이언트 생성)
        try:
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            location = os.getenv('BIGQUERY_LOCATION', 'asia-northeast3')
            
            app.system_repository = SystemRepository(project_id, location)  
            app.query_processing_repository = QueryProcessingRepository(project_id, location)
            app.chat_repository = ChatRepository(project_id, location)
            
            logger.success("Feature repositories 초기화 완료")
            
            # ChatService 초기화 (모든 의존성이 준비된 후)
            if hasattr(app, 'llm_client') and hasattr(app, 'chat_repository') and hasattr(app, 'query_processing_repository'):
                app.input_classification_service = InputClassificationService(app.llm_client)
                app.query_processing_service = QueryProcessingService(app.llm_client, app.query_processing_repository)
                app.data_analysis_service = AnalysisService(app.llm_client)
                
                app.chat_service = ChatService(
                    chat_repository=app.chat_repository,
                    classification_service=app.input_classification_service,
                    query_service=app.query_processing_service,
                    analysis_service=app.data_analysis_service
                )
                
                logger.success("ChatService가 성공적으로 초기화되었습니다")
            else:
                logger.warning("ChatService 초기화를 위한 의존성이 부족합니다")
            
            # 테이블 초기화 작업
            # 화이트리스트 테이블 확인 및 생성
            try:
                whitelist_result = app.system_repository.ensure_whitelist_table_exists()
                if whitelist_result['success']:
                    if whitelist_result.get('action') == 'created':
                        logger.created("화이트리스트 테이블이 자동 생성되었습니다")
                        logger.info("📝 관리자 계정을 수동으로 추가해야 합니다:")
                        logger.info("   SQL: INSERT INTO `nlq-ex.v1.users_whitelist` (user_id, email, status, created_at)")
                        logger.info("        VALUES ('temp_admin', 'your-email@company.com', 'active', CURRENT_TIMESTAMP());")
                    else:
                        logger.success("화이트리스트 테이블 확인 완료")
                        
                    # 화이트리스트 통계 출력
                    stats_result = app.system_repository.get_user_stats()
                    if stats_result['success']:
                        stats = stats_result['stats']
                        logger.stats(f"화이트리스트 사용자: 총 {stats['total_users']}명")
                        for status, count in stats.get('by_status', {}).items():
                            logger.info(f"   - {status}: {count}명")
                else:
                    logger.warning(f"화이트리스트 테이블 확인 실패: {whitelist_result['error']}")
            except Exception as e:
                logger.warning(f"화이트리스트 테이블 초기화 중 오류: {str(e)}")

            # 대화 저장 테이블 확인 및 생성
            try:
                conversations_result = app.chat_repository.ensure_table_exists()
                if conversations_result.get('success'):
                    action = conversations_result.get('action')
                    if action == 'created':
                        logger.created("대화 테이블이 자동 생성되었습니다")
                    else:
                        logger.success("대화 테이블 확인 완료")
                else:
                    logger.warning(f"대화 테이블 확인 실패: {conversations_result.get('error')}")
            except Exception as e:
                logger.warning(f"대화 테이블 초기화 중 오류: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Repository 초기화 실패: {str(e)}")
            
    except Exception as e:
        logger.error(f"Client initialization failed: {str(e)}")
        raise

# Initialize clients on application startup
try:
    initialize_services()
except Exception as e:
    logger.critical(f"App initialization failed: {str(e)}")

# --- Register All Routes ---
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp) 
app.register_blueprint(system_bp)

# --- Error Handlers ---

@app.errorhandler(404)
def not_found(error):
    """404 에러 핸들러 - 로그인 필수 버전"""
    logger.warning(f"404 에러 발생: {request.url}")
    
    available_endpoints = [
        "/api/health", "/api/chat", "/api/validate-sql",
        "/api/auth/google-login", "/api/auth/refresh", "/api/auth/logout",
        "/api/auth/verify",
        "/api/conversations", "/api/admin/stats"
    ]
    
    error_response = ErrorResponse.not_found_error(
        "요청하신 엔드포인트를 찾을 수 없습니다",
        details={
            "requested_url": request.url,
            "method": request.method,
            "available_endpoints": available_endpoints,
            "auth_required": "모든 API 엔드포인트는 로그인이 필요합니다"
        }
    )
    
    return jsonify(error_response), 404

@app.errorhandler(401)
def unauthorized(error):
    """401 인증 에러 핸들러"""
    logger.auth_error(f"401 인증 오류 발생: {request.url}")
    
    error_response = ErrorResponse.auth_error(
        "인증이 필요합니다. 로그인 후 이용해주세요.",
        details={
            "url": request.url,
            "method": request.method,
            "login_endpoint": "/api/auth/google-login",
            "message": "Google 계정으로 로그인하여 서비스를 이용해주세요"
        }
    )
    
    return jsonify(error_response), 401

@app.errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    import traceback
    
    # 상세한 에러 로깅
    logger.error("500 내부 서버 오류 발생:")
    logger.error(f"URL: {request.url}")
    logger.error(f"Method: {request.method}")
    logger.error(f"Error: {str(error)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # 개발 환경에서는 더 상세한 오류 정보 제공
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    details = {
        "url": request.url,
        "method": request.method
    }
    
    # 개발 모드에서만 상세 정보 추가
    if debug_mode:
        details["debug_info"] = {
            "error_message": str(error),
            "error_type": error.__class__.__name__
        }
    
    error_response = ErrorResponse.internal_error(
        "내부 서버 오류가 발생했습니다",
        details=details
    )
    
    return jsonify(error_response), 500

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """모든 예외를 캐치하는 핸들러"""
    import traceback
    
    # 상세한 에러 로깅
    logger.error("예상치 못한 오류 발생:")
    logger.error(f"URL: {request.url}")
    logger.error(f"Method: {request.method}")
    logger.error(f"Error: {str(error)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # 개발 환경 확인
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    details = {
        "url": request.url,
        "method": request.method
    }
    
    # 개발 모드에서만 상세 정보 추가
    if debug_mode:
        details["debug_info"] = {
            "error_message": str(error),
            "error_type": error.__class__.__name__,
            "traceback": traceback.format_exc().split('\n')[:10]  # 처음 10줄만
        }
    
    error_response = ErrorResponse.internal_error(
        "예상치 못한 오류가 발생했습니다",
        details=details
    )
    
    return jsonify(error_response), 500

@app.after_request
def after_request(response):
    """모든 응답에 대한 후처리"""
    try:
        # CORS 헤더 추가 (필요한 경우)
        if request.method == 'OPTIONS':
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        # 응답 데이터 확인 (스트림을 소비하지 않고)
        # Content-Length 헤더나 response.content_length로 체크
        content_length = response.content_length or 0
        has_content = content_length > 0
        
        # 스트림을 읽지 않고 상태만 확인
        if not has_content and response.status_code >= 400:
            logger.warning(f"빈 응답 감지: {request.url} ({response.status_code})")
            
            details = {
                "status_code": response.status_code,
                "url": request.url,
                "method": request.method
            }
            
            if response.status_code == 401:
                details["auth_required"] = "로그인이 필요합니다"
            
            error_response = ErrorResponse.create(
                f"HTTP {response.status_code} 오류",
                "http_error",
                details=details
            )
            
            response.set_data(json.dumps(error_response))
            response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        logger.error(f"after_request 처리 중 오류: {str(e)}")
        return response

if __name__ == '__main__':
    logger.startup("=== BigQuery AI Assistant API Server Starting ===")
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.config(f"Server starting at: http://0.0.0.0:{port}")
    logger.config(f"Debug mode: {debug_mode}")
    auth_service = getattr(app, 'auth_service', None)
    auth_enabled = auth_service and os.getenv('GOOGLE_CLIENT_ID') and os.getenv('JWT_SECRET_KEY')
    logger.config(f"Auth system: {'Enabled' if auth_enabled else 'Disabled'}")
    logger.config(f"Conversation storage: {'Enabled' if getattr(app, 'chat_repository', None) else 'Disabled'}")
    logger.config(f"Access policy: Login Required Only")
    logger.config(f"Usage limit: Unlimited for authenticated users")
    
    # 추가 설정
    if debug_mode:
        logger.warning("개발 모드에서 실행 중 - 상세 오류 정보가 포함됩니다")
        app.config['PROPAGATE_EXCEPTIONS'] = True
    
    try:
        app.run(debug=debug_mode, host='0.0.0.0', port=port)
    except Exception as e:
        logger.critical(f"서버 시작 실패: {str(e)}")
        raise
