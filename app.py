"""
BigQuery AI Assistant - API-only Backend (Refactored for Next.js)
This server only provides API endpoints and does not render HTML templates.
"""

import os
import json
import logging
import time
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import utility modules
from utils.llm_client import LLMClientFactory
from utils.bigquery_utils import BigQueryClient

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
# Allow requests from the Next.js development server
CORS(app, origins=["http://localhost:3000"], supports_credentials=True)


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
            "timestamp": datetime.datetime.now().isoformat()
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
except Exception as e:
    logger.critical(f"🚨 App initialization failed: {str(e)}")

# --- Template Rendering Routes (REMOVED) ---
# @app.route('/')
# @app.route('/landing')
# @app.route('/app')
# These routes are now handled by the Next.js frontend.

# --- API Endpoints (MAINTAINED) ---

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "3.0.0-api-only",
        "services": {
            "llm": {
                "status": "available" if llm_client else "unavailable",
                "provider": os.getenv('LLM_PROVIDER', 'anthropic')
            },
            "bigquery": {
                "status": "available" if bigquery_client else "unavailable",
                "project": os.getenv('GOOGLE_CLOUD_PROJECT', 'N/A'),
            }
        }
    }
    all_services_available = all(s["status"] == "available" for s in health_status["services"].values())
    if not all_services_available:
        health_status["status"] = "degraded"
        return jsonify(health_status), 503
    return jsonify(health_status)

@app.route('/api/chat', methods=['POST'])
def process_chat():
    """Unified chat endpoint with improved error handling"""
    start_time = time.time()
    request_id = f"req_{int(time.time())}_{id(request)}"
    
    try:
        if not request.json:
            return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
        
        message = request.json.get('message', '').strip()
        if not message:
            return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400
        
        if not llm_client:
            return jsonify(ErrorResponse.service_error("LLM client is not initialized", "llm")), 500
        
        logger.info(f"🎯 [{request_id}] Processing chat message: {message[:50]}...")
        
        # This is a simplified handler. The detailed logic from your original app.py
        # for classification and handling different categories would go here.
        # For this example, we'll assume it's a query_request.
        
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
        
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        response_data = {
            "success": True,
            "request_id": request_id,
            "result": result,
            "performance": {"execution_time_ms": execution_time_ms}
        }
        
        logger.info(f"✅ [{request_id}] Processing complete ({execution_time_ms}ms)")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ [{getattr(locals(), 'request_id', 'unknown')}] Chat processing exception: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"Server error: {str(e)}")), 500

@app.route('/api/validate-sql', methods=['POST'])
def validate_sql():
    """Validate SQL query syntax"""
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

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify(ErrorResponse.create("Endpoint not found", "not_found", {
        "available_endpoints": ["/api/health", "/api/chat", "/api/validate-sql"]
    })), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ Internal server error: {error}")
    return jsonify(ErrorResponse.internal_error("An internal server error occurred.")), 500

if __name__ == '__main__':
    logger.info("🚀 === BigQuery AI Assistant API Server Starting ===")
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Server starting at: http://0.0.0.0:{port}")
    logger.info(f"🔧 Debug mode: {debug_mode}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
