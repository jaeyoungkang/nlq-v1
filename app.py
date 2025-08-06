"""
BigQuery AI Assistant - API-only Backend (Refactored for Next.js with Authentication)
This server provides API endpoints with Google OAuth authentication and conversation management.
"""

import os
import json
import logging
import time
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, g
from flask_cors import CORS

# Import utility modules
from utils.llm_client import LLMClientFactory
from utils.bigquery_utils import BigQueryClient
from utils.auth_utils import auth_manager, require_auth, optional_auth, check_usage_limit

# --- Configuration and Logging ---

# Load environment variables from .env.local
load_dotenv('.env.local')

# Improved logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize Flask web application
app = Flask(__name__)

# --- CORS Configuration ---
# Allow requests from the Next.js development server and production domains
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, origins=allowed_origins, supports_credentials=True)

# --- Global Client Initialization ---

llm_client = None
bigquery_client = None

# Standardized error response format
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

def initialize_clients():
    """Initializes API clients with improved error handling"""
    global llm_client, bigquery_client
    
    try:
        # Initialize LLM client
        llm_provider = os.getenv('LLM_PROVIDER', 'anthropic')
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if api_key:
            llm_client = LLMClientFactory.create_client(llm_provider, {'api_key': api_key})
            logger.info(f"✅ {llm_provider} LLM client initialized successfully")
        else:
            logger.warning("⚠️ ANTHROPIC_API_KEY is not set")
        
        # Initialize BigQuery client
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('BIGQUERY_LOCATION', 'asia-northeast3')
        
        if project_id:
            bigquery_client = BigQueryClient(project_id, location)
            logger.info(f"✅ BigQuery client initialized successfully (Project: {project_id}, Location: {location})")
        else:
            logger.warning("⚠️ GOOGLE_CLOUD_PROJECT is not set")
            
    except Exception as e:
        logger.error(f"❌ Client initialization failed: {str(e)}")
        raise

# Initialize clients on application startup
try:
    initialize_clients()
    # BigQuery 클라이언트를 앱 컨텍스트에 저장 (데코레이터에서 접근 가능하도록)
    if bigquery_client:
        app.bigquery_client = bigquery_client
except Exception as e:
    logger.critical(f"🚨 App initialization failed: {str(e)}")

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

# --- 인증 관련 API 엔드포인트 ---
@app.route('/api/auth/google-login', methods=['POST'])
def google_login():
    """
    Google ID 토큰을 검증하고 JWT 토큰 발급 (세션 대화 연결 포함)
    
    Request Body:
        id_token: Google에서 받은 ID 토큰
        session_id: 현재 세션 ID (선택사항)
    
    Response:
        JWT 액세스 토큰, 리프레시 토큰, 사용자 정보, 세션 연결 결과
    """
    try:
        if not request.json or 'id_token' not in request.json:
            return jsonify(ErrorResponse.validation_error("Google ID 토큰이 필요합니다")), 400
        
        id_token_str = request.json['id_token']
        session_id = request.json.get('session_id')  # 프론트엔드에서 전달받은 세션 ID
        
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
        if session_id and bigquery_client:
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
        
        # 세션 연결 정보 추가 (있는 경우)
        if session_link_result:
            response_data["session_link"] = {
                "success": session_link_result["success"],
                "updated_conversations": session_link_result.get("updated_rows", 0),
                "message": session_link_result.get("message", "")
            }
            
            # 연결된 대화가 있으면 사용자에게 알림
            if session_link_result.get("updated_rows", 0) > 0:
                response_data["message"] = f"로그인 성공! 이전 대화 {session_link_result['updated_rows']}개가 계정에 연결되었습니다."
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Google 로그인 처리 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"로그인 처리 실패: {str(e)}")), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """
    리프레시 토큰을 사용하여 새로운 액세스 토큰 발급
    
    Request Body:
        refresh_token: 리프레시 토큰
    
    Response:
        새로운 JWT 액세스 토큰
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

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """
    사용자 로그아웃 (토큰 무효화)
    
    Headers:
        Authorization: Bearer {access_token}
    
    Response:
        로그아웃 성공 메시지
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

@app.route('/api/auth/verify', methods=['GET'])
@optional_auth
def verify_token():
    """
    JWT 토큰 유효성 검증 및 사용자 정보 반환
    
    Headers:
        Authorization: Bearer {access_token} (선택사항)
    
    Response:
        토큰 유효성, 사용자 정보
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
            
            return jsonify({
                "success": True,
                "valid": False,
                "authenticated": False,
                "usage": {
                    "daily_limit": 10,
                    "remaining": remaining,
                    "can_use": can_use
                }
            })
        
    except Exception as e:
        logger.error(f"❌ 토큰 검증 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"토큰 검증 실패: {str(e)}")), 500

@app.route('/api/auth/usage', methods=['GET'])
@optional_auth
def get_usage():
    """
    현재 사용자의 사용량 정보 조회
    
    Headers:
        Authorization: Bearer {access_token} (선택사항)
    
    Response:
        사용량 정보 (비인증 사용자만)
    """
    try:
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
                    "daily_limit": 10,
                    "used": 10 - remaining,
                    "remaining": remaining,
                    "can_use": can_use
                },
                "message": f"오늘 {remaining}회 더 이용 가능합니다" if can_use else "일일 사용 제한에 도달했습니다"
            })
        
    except Exception as e:
        logger.error(f"❌ 사용량 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"사용량 조회 실패: {str(e)}")), 500

# --- 기존 API 엔드포인트 (보안 강화) ---
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint (업데이트됨)"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": "3.2.0-auth-only-restore", # 버전 업데이트
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
            "guest_conversation_restore": False,  # 비로그인 사용자 복원 비활성화
            "authenticated_conversation_restore": True,  # 인증 사용자 복원 활성화
            "session_to_user_linking": True,  # 로그인 시 세션 연결 활성화
            "conversation_storage": True  # 대화 저장은 계속 활성화
        }
    }
    all_services_available = all(s["status"] == "available" for s in health_status["services"].values())
    if not all_services_available:
        health_status["status"] = "degraded"
        return jsonify(health_status), 503
    return jsonify(health_status)

@app.route('/api/chat', methods=['POST'])
@optional_auth
@check_usage_limit
def process_chat():
    """
    통합 채팅 엔드포인트 (인증 기능 및 대화 저장 포함)
    
    Headers:
        Authorization: Bearer {access_token} (선택사항)
    
    Request Body:
        message: 사용자 메시지
        conversation_id: 대화 ID (선택사항, 없으면 자동 생성)
        session_id: 세션 ID (선택사항, 프론트엔드에서 전달)
    
    Response:
        AI 응답, 사용량 정보, 대화 저장 결과
    """
    start_time = time.time()
    request_id = f"req_{int(time.time())}_{id(request)}"
    
    try:
        if not request.json:
            return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
        
        message = request.json.get('message', '').strip()
        conversation_id = request.json.get('conversation_id', f"conv_{int(time.time())}_{id(request)}")
        # ✅ 프론트엔드에서 전달받은 session_id 사용
        frontend_session_id = request.json.get('session_id')
        
        if not message:
            return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400
        
        if not llm_client:
            return jsonify(ErrorResponse.service_error("LLM client is not initialized", "llm")), 500
        
        logger.info(f"🎯 [{request_id}] Processing chat message: {message[:50]}...")
        logger.info(f"🔧 [{request_id}] Frontend session_id: {frontend_session_id}")
        
        # 사용자 정보 및 세션 정보 수집
        user_info = {
            'is_authenticated': g.is_authenticated,
            'user_id': g.current_user['user_id'] if g.is_authenticated else None,
            'user_email': g.current_user['email'] if g.is_authenticated else None,
            # ✅ 프론트엔드 session_id 우선 사용, 없으면 백엔드 session_id 사용
            'session_id': frontend_session_id or getattr(g, 'session_id', None),
            'ip_address': request.remote_addr or 'unknown',
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        logger.info(f"🔧 [{request_id}] Final session_id for storage: {user_info['session_id']}")
        
        # 1. 사용자 입력 분류
        classification_result = llm_client.classify_input(message)
        if not classification_result["success"]:
            # 분류 실패 시 기본적으로 SQL 쿼리로 처리
            category = "query_request"
        else:
            category = classification_result["classification"]["category"]
        
        logger.info(f"🏷️ [{request_id}] Classified as: {category}")

        result = {}
        generated_sql = None
        
        # 2. 분류 결과에 따른 기능 실행
        if category == "query_request":
            if not bigquery_client:
                raise ValueError("BigQuery client is not initialized")
            
            sql_result = llm_client.generate_sql(message, bigquery_client.project_id)
            if not sql_result["success"]:
                raise ValueError(f"SQL generation failed: {sql_result['error']}")
            
            generated_sql = sql_result["sql"]
            query_result = bigquery_client.execute_query(generated_sql)
            
            if not query_result["success"]:
                raise ValueError(f"Query execution failed: {query_result['error']}")

            result = {
                "type": "query_result",
                "generated_sql": generated_sql,
                "data": query_result["data"],
                "row_count": query_result["row_count"],
            }
        
        elif category == "metadata_request":
            if not bigquery_client:
                 raise ValueError("BigQuery client is not initialized")
            metadata = bigquery_client.get_default_table_metadata()
            response_data = llm_client.generate_metadata_response(message, metadata)
            result = {"type": "metadata_result", "content": response_data.get("response", "")}

        elif category == "data_analysis":
            # 참고: 실제 구현에서는 이전 대화의 데이터나 SQL을 전달해야 합니다.
            response_data = llm_client.analyze_data(message)
            result = {"type": "analysis_result", "content": response_data.get("analysis", "")}

        elif category == "guide_request":
            response_data = llm_client.generate_guide(message)
            result = {"type": "guide_result", "content": response_data.get("guide", "")}
            
        else: # out_of_scope
            response_data = llm_client.generate_out_of_scope(message)
            result = {"type": "out_of_scope_result", "content": response_data.get("response", "")}

        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # 3. 대화 저장 (BigQuery)
        conversation_saved = False
        if bigquery_client:
            try:
                # 사용자 메시지 저장
                user_message_data = {
                    'conversation_id': conversation_id,
                    'message_id': f"{conversation_id}_user_{int(time.time())}",
                    'user_id': user_info['user_id'],
                    'user_email': user_info['user_email'],
                    'session_id': user_info['session_id'],
                    'is_authenticated': user_info['is_authenticated'],
                    'message': message,
                    'message_type': 'user',
                    'query_type': category,
                    'generated_sql': None,
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'ip_address': user_info['ip_address'],
                    'user_agent': user_info['user_agent'],
                    'execution_time_ms': None,
                    'metadata': {'request_id': request_id}
                }
                
                # AI 응답 저장
                ai_response = result.get('content', '') or str(result)
                ai_message_data = {
                    'conversation_id': conversation_id,
                    'message_id': f"{conversation_id}_assistant_{int(time.time())}",
                    'user_id': user_info['user_id'],
                    'user_email': user_info['user_email'],
                    'session_id': user_info['session_id'],
                    'is_authenticated': user_info['is_authenticated'],
                    'message': ai_response,
                    'message_type': 'assistant',
                    'query_type': category,
                    'generated_sql': generated_sql,
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'ip_address': user_info['ip_address'],
                    'user_agent': user_info['user_agent'],
                    'execution_time_ms': execution_time_ms,
                    'metadata': {'request_id': request_id, 'result_type': result.get('type')}
                }
                
                logger.info(f"💾 [{request_id}] Saving conversation with session_id: {user_info['session_id']}")
                
                # BigQuery에 저장
                save_user_msg = bigquery_client.save_conversation(user_message_data)
                save_ai_msg = bigquery_client.save_conversation(ai_message_data)
                
                conversation_saved = save_user_msg['success'] and save_ai_msg['success']
                
                if not conversation_saved:
                    logger.warning(f"⚠️ [{request_id}] 대화 저장 실패")
                else:
                    logger.info(f"✅ [{request_id}] 대화 저장 완료")
                
            except Exception as e:
                logger.error(f"❌ [{request_id}] 대화 저장 중 오류: {str(e)}")
        
        # 4. 응답 구성
        response_data = {
            "success": True,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "result": result,
            "performance": {"execution_time_ms": execution_time_ms},
            "conversation_saved": conversation_saved
        }
        
        # 5. 사용량 정보 추가 (비인증 사용자만)
        if not g.is_authenticated:
            remaining_usage = getattr(g, 'remaining_usage', 0)
            response_data["usage"] = {
                "daily_limit": 10,
                "remaining": remaining_usage,
                "message": f"오늘 {remaining_usage}회 더 이용 가능합니다" if remaining_usage > 0 else "일일 사용 제한에 도달했습니다"
            }
        else:
            response_data["usage"] = {
                "unlimited": True,
                "message": "인증된 사용자는 무제한 이용 가능합니다"
            }
        
        logger.info(f"✅ [{request_id}] Processing complete ({execution_time_ms}ms)")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ [{getattr(locals(), 'request_id', 'unknown')}] Chat processing exception: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"Server error: {str(e)}")), 500

@app.route('/api/conversations', methods=['GET'])
@require_auth
def get_user_conversations():
    """
    인증된 사용자의 대화 히스토리 목록 조회
    
    Headers:
        Authorization: Bearer {access_token}
    
    Query Parameters:
        limit: 최대 조회 개수 (기본값: 50)
        offset: 오프셋 (기본값: 0)
    
    Response:
        대화 세션 목록
    """
    try:
        user_id = g.current_user['user_id']
        limit = min(int(request.args.get('limit', 50)), 100)  # 최대 100개로 제한
        offset = int(request.args.get('offset', 0))
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        # 대화 히스토리 조회
        conversations_result = bigquery_client.get_user_conversations(user_id, limit, offset)
        
        if not conversations_result['success']:
            return jsonify(ErrorResponse.service_error(
                conversations_result['error'], "bigquery"
            )), 500
        
        logger.info(f"📋 대화 히스토리 조회: {g.current_user['email']} ({conversations_result['count']}개)")
        
        return jsonify({
            "success": True,
            "conversations": conversations_result['conversations'],
            "count": conversations_result['count'],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": conversations_result['count'] == limit
            }
        })
        
    except ValueError as e:
        return jsonify(ErrorResponse.validation_error(str(e))), 400
    except Exception as e:
        logger.error(f"❌ 대화 히스토리 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"대화 히스토리 조회 실패: {str(e)}")), 500

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@require_auth
def get_conversation_details(conversation_id):
    """
    특정 대화 세션의 상세 내역 조회
    
    Headers:
        Authorization: Bearer {access_token}
    
    Path Parameters:
        conversation_id: 대화 ID
    
    Response:
        해당 세션의 모든 메시지
    """
    try:
        user_id = g.current_user['user_id']
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        # 대화 상세 조회 (사용자 권한 확인 포함)
        details_result = bigquery_client.get_conversation_details(conversation_id, user_id)
        
        if not details_result['success']:
            return jsonify(ErrorResponse.service_error(
                details_result['error'], "bigquery"
            )), 500
        
        if details_result['message_count'] == 0:
            return jsonify(ErrorResponse.create(
                "대화를 찾을 수 없거나 접근 권한이 없습니다", "not_found"
            )), 404
        
        logger.info(f"📖 대화 상세 조회: {conversation_id} ({details_result['message_count']}개 메시지)")
        
        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "messages": details_result['messages'],
            "message_count": details_result['message_count']
        })
        
    except Exception as e:
        logger.error(f"❌ 대화 상세 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"대화 상세 조회 실패: {str(e)}")), 500

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@require_auth
def delete_conversation(conversation_id):
    """
    특정 대화 세션 삭제
    
    Headers:
        Authorization: Bearer {access_token}
    
    Path Parameters:
        conversation_id: 삭제할 대화 ID
    
    Response:
        삭제 성공 메시지
    """
    try:
        user_id = g.current_user['user_id']
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        # 대화 삭제 (사용자 권한 확인 포함)
        delete_result = bigquery_client.delete_conversation(conversation_id, user_id)
        
        if not delete_result['success']:
            if "찾을 수 없습니다" in delete_result['error']:
                return jsonify(ErrorResponse.create(
                    "대화를 찾을 수 없거나 삭제 권한이 없습니다", "not_found"
                )), 404
            else:
                return jsonify(ErrorResponse.service_error(
                    delete_result['error'], "bigquery"
                )), 500
        
        logger.info(f"🗑️ 대화 삭제 완료: {conversation_id} (사용자: {g.current_user['email']})")
        
        return jsonify({
            "success": True,
            "message": delete_result['message'],
            "deleted_rows": delete_result.get('deleted_rows', 0)
        })
        
    except Exception as e:
        logger.error(f"❌ 대화 삭제 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"대화 삭제 실패: {str(e)}")), 500

@app.route('/api/admin/stats', methods=['GET'])
@require_auth
def get_system_stats():
    """
    시스템 통계 조회 (관리자용)
    
    Headers:
        Authorization: Bearer {access_token}
    
    Response:
        시스템 사용량 및 통계
    """
    try:
        # 관리자 권한 확인 (선택사항 - 특정 이메일 도메인만 허용)
        user_email = g.current_user.get('email', '')
        # admin_domains = os.getenv('ADMIN_EMAIL_DOMAINS', '').split(',')
        # if admin_domains and not any(user_email.endswith(domain.strip()) for domain in admin_domains):
        #     return jsonify(ErrorResponse.create("관리자 권한이 필요합니다", "insufficient_permissions")), 403
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
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
            'llm_status': 'available' if llm_client else 'unavailable',
            'bigquery_status': 'available' if bigquery_client else 'unavailable',
            'auth_status': 'available' if auth_manager.google_client_id and auth_manager.jwt_secret else 'unavailable'
        }
        
        # 4. 환경 설정
        stats['config'] = {
            'daily_usage_limit': int(os.getenv('DAILY_USAGE_LIMIT', '10')),
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

@app.route('/api/validate-sql', methods=['POST'])
@optional_auth
def validate_sql():
    """
    SQL 쿼리 문법 검증 (선택적 인증)
    
    Headers:
        Authorization: Bearer {access_token} (선택사항)
    
    Request Body:
        sql: 검증할 SQL 쿼리
    
    Response:
        SQL 검증 결과
    """
    try:
        if not request.json or 'sql' not in request.json:
            return jsonify(ErrorResponse.validation_error("SQL query is required")), 400
        
        sql_query = request.json['sql'].strip()
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        validation_result = bigquery_client.validate_query(sql_query)
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"❌ SQL validation error: {str(e)}")
        return jsonify(ErrorResponse.service_error(f"Validation error: {str(e)}", "bigquery")), 500

@app.route('/api/conversations/session/<session_id>/<conversation_id>', methods=['GET'])
def get_session_conversation_details(session_id, conversation_id):
    """
    비인증 사용자의 특정 대화 세션 상세 조회
    
    Path Parameters:
        session_id: 세션 ID
        conversation_id: 대화 ID
    
    Response:
        해당 세션의 특정 대화 메시지들
    """
    try:
        # 세션 ID 및 대화 ID 유효성 검증
        if not session_id or len(session_id) < 10:
            return jsonify(ErrorResponse.validation_error("유효하지 않은 세션 ID입니다")), 400
        
        if not conversation_id:
            return jsonify(ErrorResponse.validation_error("대화 ID가 필요합니다")), 400
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        # 세션 대화 상세 조회 (세션 권한 확인 포함)
        details_result = bigquery_client.get_session_conversation_details(conversation_id, session_id)
        
        if not details_result['success']:
            return jsonify(ErrorResponse.service_error(
                details_result['error'], "bigquery"
            )), 500
        
        if details_result['message_count'] == 0:
            return jsonify(ErrorResponse.create(
                "대화를 찾을 수 없거나 접근 권한이 없습니다", "not_found"
            )), 404
        
        logger.info(f"📖 세션 대화 상세 조회: {session_id}/{conversation_id} ({details_result['message_count']}개 메시지)")
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "conversation_id": conversation_id,
            "messages": details_result['messages'],
            "message_count": details_result['message_count']
        })
        
    except Exception as e:
        logger.error(f"❌ 세션 대화 상세 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"세션 대화 상세 조회 실패: {str(e)}")), 500

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    available_endpoints = [
        "/api/health", "/api/chat", "/api/validate-sql",
        "/api/auth/google-login", "/api/auth/refresh", "/api/auth/logout",
        "/api/auth/verify", "/api/auth/usage",
        "/api/conversations"
    ]
    return jsonify(ErrorResponse.create("Endpoint not found", "not_found", {
        "available_endpoints": available_endpoints
    })), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Internal server error: {error}")
    return jsonify(ErrorResponse.internal_error("An internal server error occurred.")), 500

# --- Periodic Cleanup Task ---
@app.before_request
def before_request():
    """각 요청 전에 실행되는 정리 작업"""
    try:
        # 만료된 세션 정리 (확률적으로 실행)
        import random
        if random.random() < 0.01:  # 1% 확률로 정리 실행
            auth_manager.cleanup_expired_sessions()
    except Exception as e:
        logger.warning(f"⚠️ 세션 정리 중 오류: {str(e)}")

if __name__ == '__main__':
    logger.info("🚀 === BigQuery AI Assistant API Server Starting ===")
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Server starting at: http://0.0.0.0:{port}")
    logger.info(f"🔧 Debug mode: {debug_mode}")
    logger.info(f"🔐 Auth system: {'Enabled' if auth_manager.google_client_id and auth_manager.jwt_secret else 'Disabled'}")
    logger.info(f"📊 Conversation storage: {'Enabled' if bigquery_client else 'Disabled'}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)