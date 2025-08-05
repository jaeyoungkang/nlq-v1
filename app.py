"""
BigQuery AI Assistant - 메인 애플리케이션 (LLM 통합 버전)
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

# 유틸리티 모듈 임포트
from utils.llm_client import LLMClientFactory
from utils.bigquery_utils import BigQueryClient

# --- 설정 및 로깅 ---

# .env.local 파일에서 환경변수 로드
load_dotenv('.env.local')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

def initialize_clients():
    """API 클라이언트들을 초기화"""
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

# 애플리케이션 시작 시 클라이언트 초기화
initialize_clients()

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
    """헬스 체크 엔드포인트"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "2.0.0-llm",
        "services": {
            "llm": "available" if llm_client else "unavailable",
            "bigquery": "available" if bigquery_client else "unavailable"
        }
    })

@app.route('/api/chat', methods=['POST'])
def process_chat():
    """통합 채팅 엔드포인트 - 사용자 입력을 분류하여 적절한 처리 수행"""
    start_time = time.time()
    
    try:
        # 요청 데이터 검증
        if not request.json:
            return jsonify({
                "success": False,
                "error": "JSON 데이터가 필요합니다"
            }), 400
        
        message = request.json.get('message', '').strip()
        context = request.json.get('context', {})  # 이전 대화 컨텍스트
        
        if not message:
            return jsonify({
                "success": False,
                "error": "메시지를 입력해주세요"
            }), 400
        
        # 클라이언트 상태 확인
        if not llm_client:
            return jsonify({
                "success": False,
                "error": "LLM 클라이언트가 초기화되지 않았습니다"
            }), 500
        
        logger.info(f"채팅 메시지 처리 시작: {message}")
        
        # 1단계: 사용자 입력 분류
        classification_result = llm_client.classify_input(message)
        
        if not classification_result["success"]:
            return jsonify({
                "success": False,
                "error": f"입력 분류 실패: {classification_result['error']}",
                "step": "classification"
            }), 500
        
        classification = classification_result["classification"]
        category = classification["category"]
        
        logger.info(f"입력 분류 결과: {category} (신뢰도: {classification['confidence']})")
        
        # 2단계: 카테고리별 처리
        if category == "query_request":
            result = handle_query_request(message, context)
        elif category == "metadata_request":
            result = handle_metadata_request(message, context)
        elif category == "data_analysis":
            result = handle_data_analysis(message, context)
        elif category == "guide_request":
            result = handle_guide_request(message, context)
        else:  # out_of_scope
            result = handle_out_of_scope(message, context)
        
        # 실행 시간 계산
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # 통합 응답
        return jsonify({
            "success": True,
            "message": message,
            "category": category,
            "classification": classification,
            "result": result,
            "execution_time_ms": execution_time_ms,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"채팅 처리 중 오류: {str(e)}")
        
        return jsonify({
            "success": False,
            "error": f"서버 오류: {str(e)}",
            "execution_time_ms": execution_time_ms,
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

def handle_query_request(message: str, context: dict) -> dict:
    """쿼리 생성 요청 처리"""
    try:
        if not bigquery_client:
            return {
                "type": "error",
                "error": "BigQuery 클라이언트가 초기화되지 않았습니다"
            }
        
        # SQL 생성
        sql_result = llm_client.generate_sql(message, bigquery_client.project_id)
        
        if not sql_result["success"]:
            return {
                "type": "error",
                "error": f"SQL 생성 실패: {sql_result['error']}"
            }
        
        generated_sql = sql_result["sql"]
        logger.info(f"생성된 SQL: {generated_sql}")
        
        # BigQuery 실행
        query_result = bigquery_client.execute_query(generated_sql)
        
        if not query_result["success"]:
            return {
                "type": "error",
                "error": f"쿼리 실행 실패: {query_result['error']}",
                "generated_sql": generated_sql
            }
        
        return {
            "type": "query_result",
            "generated_sql": generated_sql,
            "data": query_result["data"],
            "row_count": query_result["row_count"],
            "stats": query_result.get("stats", {})
        }
        
    except Exception as e:
        logger.error(f"쿼리 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_metadata_request(message: str, context: dict) -> dict:
    """메타데이터 요청 처리"""
    try:
        if not bigquery_client:
            return {
                "type": "error",
                "error": "BigQuery 클라이언트가 초기화되지 않았습니다"
            }
        
        # 기본 테이블 메타데이터 조회
        metadata_result = bigquery_client.get_default_table_metadata()
        
        if not metadata_result["success"]:
            return {
                "type": "error",
                "error": f"메타데이터 조회 실패: {metadata_result['error']}"
            }
        
        # LLM으로 사용자 친화적 응답 생성
        response_result = llm_client.generate_metadata_response(message, metadata_result)
        
        if not response_result["success"]:
            return {
                "type": "error",
                "error": f"메타데이터 응답 생성 실패: {response_result['error']}"
            }
        
        return {
            "type": "metadata",
            "response": response_result["response"],
            "raw_metadata": metadata_result  # 원본 메타데이터도 포함
        }
        
    except Exception as e:
        logger.error(f"메타데이터 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_data_analysis(message: str, context: dict) -> dict:
    """데이터 분석 요청 처리"""
    try:
        previous_data = context.get("previous_data", [])
        previous_sql = context.get("previous_sql", "")
        
        analysis_result = llm_client.analyze_data(
            message, previous_data, previous_sql
        )
        
        if not analysis_result["success"]:
            return {
                "type": "error",
                "error": f"데이터 분석 실패: {analysis_result['error']}"
            }
        
        return {
            "type": "analysis",
            "analysis": analysis_result["analysis"]
        }
        
    except Exception as e:
        logger.error(f"데이터 분석 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_guide_request(message: str, context: dict) -> dict:
    """가이드 요청 처리"""
    try:
        context_info = f"사용자가 BigQuery Assistant를 사용 중"
        if context.get("previous_queries"):
            context_info += f", 이전에 {len(context['previous_queries'])}개의 쿼리 실행"
        
        guide_result = llm_client.generate_guide(message, context_info)
        
        if not guide_result["success"]:
            return {
                "type": "error",
                "error": f"가이드 생성 실패: {guide_result['error']}"
            }
        
        return {
            "type": "guide",
            "guide": guide_result["guide"]
        }
        
    except Exception as e:
        logger.error(f"가이드 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

def handle_out_of_scope(message: str, context: dict) -> dict:
    """기능 범위 외 요청 처리"""
    try:
        scope_result = llm_client.generate_out_of_scope(message)
        
        if not scope_result["success"]:
            return {
                "type": "error",
                "error": f"범위 외 응답 생성 실패: {scope_result['error']}"
            }
        
        return {
            "type": "out_of_scope",
            "response": scope_result["response"]
        }
        
    except Exception as e:
        logger.error(f"범위 외 요청 처리 중 오류: {str(e)}")
        return {
            "type": "error",
            "error": str(e)
        }

@app.route('/api/validate-sql', methods=['POST'])
def validate_sql():
    """SQL 쿼리 문법 검증 (실행하지 않음)"""
    try:
        if not request.json or 'sql' not in request.json:
            return jsonify({
                "success": False,
                "error": "SQL 쿼리가 필요합니다"
            }), 400
        
        sql_query = request.json['sql'].strip()
        
        if not bigquery_client:
            return jsonify({
                "success": False,
                "error": "BigQuery 클라이언트가 초기화되지 않았습니다"
            }), 500
        
        # 드라이 런으로 SQL 검증
        validation_result = bigquery_client.validate_query(sql_query)
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"SQL 검증 중 오류: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"검증 중 오류: {str(e)}"
        }), 500

@app.errorhandler(404)
def not_found(error):
    """404 오류 핸들러"""
    return jsonify({
        "success": False,
        "error": "요청한 엔드포인트를 찾을 수 없습니다",
        "available_endpoints": [
            "GET /",
            "GET /api/health", 
            "POST /api/chat",
            "POST /api/validate-sql"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500 오류 핸들러"""
    logger.error(f"내부 서버 오류: {error}")
    return jsonify({
        "success": False,
        "error": "내부 서버 오류가 발생했습니다",
        "timestamp": datetime.datetime.now().isoformat()
    }), 500

if __name__ == '__main__':
    logger.info("=== BigQuery AI Assistant 서버 시작 (LLM 통합 버전) ===")
    logger.info(f"LLM: {'✅ 사용 가능' if llm_client else '❌ 사용 불가'}")
    logger.info(f"BigQuery: {'✅ 사용 가능' if bigquery_client else '❌ 사용 불가'}")
    
    # Cloud Run에서는 PORT 환경변수 사용
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"서버 시작: http://0.0.0.0:{port}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)