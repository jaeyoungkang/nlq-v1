"""
BigQuery AI Assistant - 메인 애플리케이션 (리팩토링 버전)
LLM 클라이언트 통합 및 에러 핸들링 개선
"""

import os
import json
import logging
import time
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# 통합된 유틸리티 모듈 임포트
from utils.llm_client import LLMClientFactory
from utils.bigquery_utils import BigQueryClient

# --- 설정 및 로깅 ---

# .env.local 파일에서 환경변수 로드
load_dotenv('.env.local')

# 개선된 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Flask 웹 애플리케이션 초기화
app = Flask(__name__)
CORS(app, 
     origins=["http://localhost:8080", "http://127.0.0.1:8080"],
     allow_headers=["Content-Type", "Cache-Control"],
     expose_headers=["Cache-Control"],
     supports_credentials=False)

# --- 글로벌 클라이언트 초기화 ---

# 글로벌 클라이언트 인스턴스
llm_client = None
bigquery_client = None

# 표준화된 에러 응답 포맷
class ErrorResponse:
    """표준화된 에러 응답 클래스"""
    
    @staticmethod
    def create(error_message: str, error_type: str = "general", details: dict = None):
        """표준화된 에러 응답 생성"""
        return {
            "success": False,
            "error": error_message,
            "error_type": error_type,
            "details": details or {},
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    @staticmethod
    def validation_error(message: str):
        """입력 검증 에러"""
        return ErrorResponse.create(message, "validation_error")
    
    @staticmethod
    def service_error(message: str, service: str):
        """서비스별 에러"""
        return ErrorResponse.create(message, "service_error", {"service": service})
    
    @staticmethod
    def internal_error(message: str):
        """내부 서버 에러"""
        return ErrorResponse.create(message, "internal_error")

def initialize_clients():
    """API 클라이언트들을 초기화 (개선된 에러 핸들링)"""
    global llm_client, bigquery_client
    
    try:
        # LLM 클라이언트 초기화
        llm_provider = os.getenv('LLM_PROVIDER', 'anthropic')
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if api_key:
            llm_client = LLMClientFactory.create_client(llm_provider, {'api_key': api_key})
            logger.info(f"✅ {llm_provider} LLM 클라이언트 초기화 완료")
        else:
            logger.warning("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다")
        
        # BigQuery 클라이언트 초기화
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('BIGQUERY_LOCATION', 'asia-northeast3')
        
        if project_id:
            bigquery_client = BigQueryClient(project_id, location)
            logger.info(f"✅ BigQuery 클라이언트 초기화 완료 (프로젝트: {project_id}, 리전: {location})")
        else:
            logger.warning("⚠️ GOOGLE_CLOUD_PROJECT가 설정되지 않았습니다")
            
    except Exception as e:
        logger.error(f"❌ 클라이언트 초기화 실패: {str(e)}")
        raise

# 애플리케이션 시작 시 클라이언트 초기화
try:
    initialize_clients()
except Exception as e:
    logger.critical(f"🚨 앱 초기화 실패: {str(e)}")

@app.route('/')
def index():
    """메인 페이지 - 랜딩 페이지로 리다이렉트"""
    return render_template('landing.html')

@app.route('/landing')
def landing_page():
    """랜딩 페이지"""
    return render_template('landing.html')

@app.route('/app')
def chat_app():
    """채팅 애플리케이션"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트 (개선된 버전)"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "2.1.0-refactored",
        "services": {
            "llm": {
                "status": "available" if llm_client else "unavailable",
                "provider": os.getenv('LLM_PROVIDER', 'anthropic')
            },
            "bigquery": {
                "status": "available" if bigquery_client else "unavailable",
                "project": os.getenv('GOOGLE_CLOUD_PROJECT', 'N/A'),
                "location": os.getenv('BIGQUERY_LOCATION', 'asia-northeast3')
            }
        },
        "environment": {
            "flask_env": os.getenv('FLASK_ENV', 'production'),
            "debug_mode": app.debug
        }
    }
    
    # 전체 서비스 상태 판단
    all_services_available = all(
        service["status"] == "available" 
        for service in health_status["services"].values()
    )
    
    if not all_services_available:
        health_status["status"] = "degraded"
        return jsonify(health_status), 503
    
    return jsonify(health_status)

@app.route('/api/chat', methods=['POST'])
def process_chat():
    """
    통합 채팅 엔드포인트 (개선된 에러 핸들링)
    사용자 입력을 분류하여 적절한 처리 수행
    """
    start_time = time.time()
    request_id = f"req_{int(time.time())}_{id(request)}"
    
    try:
        # 요청 데이터 검증
        if not request.json:
            return jsonify(ErrorResponse.validation_error("JSON 데이터가 필요합니다")), 400
        
        message = request.json.get('message', '').strip()
        context = request.json.get('context', {})
        
        if not message:
            return jsonify(ErrorResponse.validation_error("메시지를 입력해주세요")), 400
        
        if len(message) > 1000:
            return jsonify(ErrorResponse.validation_error("메시지가 너무 깁니다 (최대 1000자)")), 400
        
        # 클라이언트 상태 확인
        if not llm_client:
            return jsonify(ErrorResponse.service_error(
                "LLM 클라이언트가 초기화되지 않았습니다", "llm"
            )), 500
        
        logger.info(f"🎯 [{request_id}] 채팅 메시지 처리 시작: {message[:50]}...")
        
        # 1단계: 사용자 입력 분류 (개선된 에러 핸들링)
        classification_result = llm_client.classify_input(message)
        
        if not classification_result["success"]:
            logger.error(f"❌ [{request_id}] 입력 분류 실패: {classification_result.get('error')}")
            return jsonify(ErrorResponse.service_error(
                f"입력 분류 실패: {classification_result['error']}", "llm"
            )), 500
        
        classification = classification_result["classification"]
        category = classification["category"]
        
        logger.info(f"📋 [{request_id}] 입력 분류: {category} (신뢰도: {classification['confidence']})")
        
        # 2단계: 카테고리별 처리 (에러 핸들링 개선)
        try:
            if category == "query_request":
                result = handle_query_request(message, context, request_id)
            elif category == "metadata_request":
                result = handle_metadata_request(message, context, request_id)
            elif category == "data_analysis":
                result = handle_data_analysis(message, context, request_id)
            elif category == "guide_request":
                result = handle_guide_request(message, context, request_id)
            else:  # out_of_scope
                result = handle_out_of_scope(message, context, request_id)
                
        except Exception as e:
            logger.error(f"❌ [{request_id}] 카테고리 처리 중 오류: {str(e)}")
            return jsonify(ErrorResponse.service_error(
                f"요청 처리 중 오류가 발생했습니다: {str(e)}", category
            )), 500
        
        # 실행 시간 계산
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # 성공 응답 (표준화된 포맷)
        response_data = {
            "success": True,
            "request_id": request_id,
            "message": message,
            "category": category,
            "classification": classification,
            "result": result,
            "performance": {
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }
        
        logger.info(f"✅ [{request_id}] 처리 완료 ({execution_time_ms}ms)")
        return jsonify(response_data)
        
    except Exception as e:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"❌ [{getattr(locals(), 'request_id', 'unknown')}] 채팅 처리 중 예외: {str(e)}")
        
        error_response = ErrorResponse.internal_error(f"서버 오류: {str(e)}")
        error_response["performance"] = {
            "execution_time_ms": execution_time_ms,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return jsonify(error_response), 500

def handle_query_request(message: str, context: dict, request_id: str) -> dict:
    """쿼리 생성 요청 처리 (개선된 에러 핸들링)"""
    try:
        if not bigquery_client:
            raise ValueError("BigQuery 클라이언트가 초기화되지 않았습니다")
        
        # SQL 생성
        logger.info(f"🔧 [{request_id}] SQL 생성 시작")
        sql_result = llm_client.generate_sql(message, bigquery_client.project_id)
        
        if not sql_result["success"]:
            raise ValueError(f"SQL 생성 실패: {sql_result['error']}")
        
        generated_sql = sql_result["sql"]
        logger.info(f"📝 [{request_id}] 생성된 SQL: {generated_sql[:100]}...")
        
        # BigQuery 실행
        logger.info(f"⚡ [{request_id}] BigQuery 쿼리 실행 시작")
        query_result = bigquery_client.execute_query(generated_sql)
        
        if not query_result["success"]:
            # BigQuery 에러 타입별 처리
            error_type = query_result.get("error_type", "execution_error")
            raise ValueError(f"쿼리 실행 실패 ({error_type}): {query_result['error']}")
        
        logger.info(f"✅ [{request_id}] 쿼리 실행 완료: {query_result['row_count']}행")
        
        return {
            "type": "query_result",
            "generated_sql": generated_sql,
            "data": query_result["data"],
            "row_count": query_result["row_count"],
            "stats": query_result.get("stats", {})
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] 쿼리 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e),
            "generated_sql": locals().get("generated_sql", None)
        }

def handle_metadata_request(message: str, context: dict, request_id: str) -> dict:
    """메타데이터 요청 처리 (개선된 에러 핸들링)"""
    try:
        if not bigquery_client:
            raise ValueError("BigQuery 클라이언트가 초기화되지 않았습니다")
        
        # 메타데이터 조회
        logger.info(f"📋 [{request_id}] 메타데이터 조회 시작")
        metadata_result = bigquery_client.get_default_table_metadata()
        
        if not metadata_result["success"]:
            raise ValueError(f"메타데이터 조회 실패: {metadata_result['error']}")
        
        # LLM으로 사용자 친화적 응답 생성
        logger.info(f"🤖 [{request_id}] 메타데이터 응답 생성 시작")
        response_result = llm_client.generate_metadata_response(message, metadata_result)
        
        if not response_result["success"]:
            raise ValueError(f"메타데이터 응답 생성 실패: {response_result['error']}")
        
        logger.info(f"✅ [{request_id}] 메타데이터 응답 생성 완료")
        
        return {
            "type": "metadata",
            "response": response_result["response"],
            "raw_metadata": metadata_result
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] 메타데이터 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_data_analysis(message: str, context: dict, request_id: str) -> dict:
    """데이터 분석 요청 처리 (개선된 에러 핸들링)"""
    try:
        previous_data = context.get("previous_data", [])
        previous_sql = context.get("previous_sql", "")
        
        logger.info(f"🔍 [{request_id}] 데이터 분석 시작 (데이터: {len(previous_data)}행)")
        
        analysis_result = llm_client.analyze_data(message, previous_data, previous_sql)
        
        if not analysis_result["success"]:
            raise ValueError(f"데이터 분석 실패: {analysis_result['error']}")
        
        logger.info(f"✅ [{request_id}] 데이터 분석 완료")
        
        return {
            "type": "analysis",
            "analysis": analysis_result["analysis"]
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] 데이터 분석 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_guide_request(message: str, context: dict, request_id: str) -> dict:
    """가이드 요청 처리 (개선된 에러 핸들링)"""
    try:
        context_info = f"사용자가 BigQuery Assistant를 사용 중"
        if context.get("previous_queries"):
            context_info += f", 이전에 {len(context['previous_queries'])}개의 쿼리 실행"
        
        logger.info(f"💡 [{request_id}] 가이드 응답 생성 시작")
        
        guide_result = llm_client.generate_guide(message, context_info)
        
        if not guide_result["success"]:
            raise ValueError(f"가이드 생성 실패: {guide_result['error']}")
        
        logger.info(f"✅ [{request_id}] 가이드 응답 생성 완료")
        
        return {
            "type": "guide",
            "guide": guide_result["guide"]
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] 가이드 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_out_of_scope(message: str, context: dict, request_id: str) -> dict:
    """기능 범위 외 요청 처리 (개선된 에러 핸들링)"""
    try:
        logger.info(f"🚫 [{request_id}] 범위 외 요청 처리")
        
        scope_result = llm_client.generate_out_of_scope(message)
        
        if not scope_result["success"]:
            raise ValueError(f"범위 외 응답 생성 실패: {scope_result['error']}")
        
        logger.info(f"✅ [{request_id}] 범위 외 응답 생성 완료")
        
        return {
            "type": "out_of_scope",
            "response": scope_result["response"]
        }
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] 범위 외 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

@app.route('/api/validate-sql', methods=['POST'])
def validate_sql():
    """SQL 쿼리 문법 검증 (개선된 에러 핸들링)"""
    request_id = f"val_{int(time.time())}"
    
    try:
        if not request.json or 'sql' not in request.json:
            return jsonify(ErrorResponse.validation_error("SQL 쿼리가 필요합니다")), 400
        
        sql_query = request.json['sql'].strip()
        
        if len(sql_query) > 10000:
            return jsonify(ErrorResponse.validation_error("SQL 쿼리가 너무 깁니다 (최대 10,000자)")), 400
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error(
                "BigQuery 클라이언트가 초기화되지 않았습니다", "bigquery"
            )), 500
        
        logger.info(f"🔍 [{request_id}] SQL 검증 시작: {sql_query[:50]}...")
        
        # 드라이 런으로 SQL 검증
        validation_result = bigquery_client.validate_query(sql_query)
        
        if validation_result["success"]:
            logger.info(f"✅ [{request_id}] SQL 검증 완료")
        else:
            logger.warning(f"⚠️ [{request_id}] SQL 검증 실패: {validation_result.get('error')}")
        
        validation_result["request_id"] = request_id
        validation_result["timestamp"] = datetime.datetime.now().isoformat()
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] SQL 검증 중 오류: {str(e)}")
        error_response = ErrorResponse.service_error(f"검증 중 오류: {str(e)}", "bigquery")
        error_response["request_id"] = request_id
        return jsonify(error_response), 500

@app.errorhandler(404)
def not_found(error):
    """404 오류 핸들러 (개선된 버전)"""
    return jsonify(ErrorResponse.create(
        "요청한 엔드포인트를 찾을 수 없습니다",
        "not_found",
        {
            "available_endpoints": [
                "GET /",
                "GET /landing", 
                "GET /app",
                "GET /api/health", 
                "POST /api/chat",
                "POST /api/validate-sql"
            ],
            "method": request.method,
            "path": request.path
        }
    )), 404

@app.errorhandler(500)
def internal_error(error):
    """500 오류 핸들러 (개선된 버전)"""
    logger.error(f"❌ 내부 서버 오류: {error}")
    return jsonify(ErrorResponse.internal_error(
        "내부 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    )), 500

@app.errorhandler(413)
def request_too_large(error):
    """413 오류 핸들러 (요청 크기 초과)"""
    return jsonify(ErrorResponse.validation_error(
        "요청 크기가 너무 큽니다. 파일 크기를 줄여주세요."
    )), 413

@app.errorhandler(429)
def rate_limit_exceeded(error):
    """429 오류 핸들러 (요청 제한 초과)"""
    return jsonify(ErrorResponse.create(
        "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
        "rate_limit_exceeded"
    )), 429

if __name__ == '__main__':
    logger.info("🚀 === BigQuery AI Assistant 서버 시작 (리팩토링 버전) ===")
    logger.info(f"LLM: {'✅ 사용 가능' if llm_client else '❌ 사용 불가'}")
    logger.info(f"BigQuery: {'✅ 사용 가능' if bigquery_client else '❌ 사용 불가'}")
    
    # Cloud Run에서는 PORT 환경변수 사용
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 서버 시작: http://0.0.0.0:{port}")
    logger.info(f"🔧 디버그 모드: {debug_mode}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)