# backend/routes/chat_routes.py
"""
채팅 및 대화 관련 라우트 - 스키마 정리 계획 적용
"""

import os
import time
import json
import logging
import datetime
import uuid
from flask import Blueprint, request, jsonify, g, Response
from utils.auth_utils import require_auth
from utils.error_utils import ErrorResponse

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/api')

def create_sse_event(event_type: str, data: dict) -> str:
    """SSE 이벤트 형식으로 데이터 생성"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@chat_bp.route('/chat-stream', methods=['POST'])
@require_auth
def process_chat_stream():
    """SSE 스트리밍 채팅 엔드포인트 (인증된 사용자 전용)"""
    if not request.json:
        return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
    
    message = request.json.get('message', '').strip()
    conversation_id = request.json.get('conversation_id', f"conv_{int(time.time())}_{uuid.uuid4().hex[:6]}")
    
    if not message:
        return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400

    def generate_stream():
        start_time = time.time()
        request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        try:
            from flask import current_app
            llm_client = getattr(current_app, 'llm_client', None)
            bigquery_client = getattr(current_app, 'bigquery_client', None)
            
            if not llm_client or not bigquery_client:
                yield create_sse_event('error', {'error': 'Service client not initialized', 'error_type': 'service_error'})
                return
            
            logger.info(f"🎯 [{request_id}] Processing streaming chat: {message[:50]}...")
            
            user_info = {'user_id': g.current_user['user_id'], 'email': g.current_user['email']}
            
            # (컨텍스트 로직은 기존과 유사하게 유지)
            conversation_context = []
            # ... (컨텍스트 로드 로직) ...

            # 1. 사용자 메시지 저장
            user_message_data = {
                'conversation_id': conversation_id,
                'message_id': f"{conversation_id}_user_{int(time.time())}",
                'user_id': user_info['user_id'],
                'message': message,
                'message_type': 'user',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            bigquery_client.save_conversation(user_message_data)

            # 2. 입력 분류
            yield create_sse_event('progress', {'stage': 'classification', 'message': '🔍 입력 분류 중...'})
            classification_result = llm_client.classify_input(message, conversation_context)
            category = classification_result.get("classification", {}).get("category", "query_request")
            logger.info(f"🏷️ [{request_id}] Classified as: {category}")
            
            result = {}
            generated_sql = None
            query_id = None
            
            # 3. 분류에 따른 처리
            if category == "query_request":
                yield create_sse_event('progress', {'stage': 'sql_generation', 'message': '📝 SQL 생성 중...'})
                sql_result = llm_client.generate_sql(message, bigquery_client.project_id, None, conversation_context)
                if not sql_result["success"]:
                    raise ValueError(f"SQL generation failed: {sql_result.get('error')}")
                
                generated_sql = sql_result["sql"]
                query_id = str(uuid.uuid4()) # 쿼리 ID 생성
                
                yield create_sse_event('progress', {'stage': 'query_execution', 'message': '⚡ 쿼리 실행 중...'})
                query_result = bigquery_client.execute_query(generated_sql)
                
                # 쿼리 결과 저장
                save_res = bigquery_client.save_query_result(query_id, query_result)
                if not save_res['success']:
                     logger.warning(f"⚠️ [{request_id}] 쿼리 결과 저장 실패: {save_res.get('error')}")

                result = {
                    "type": "query_result",
                    "generated_sql": generated_sql,
                    "data": query_result.get("data", []),
                    "row_count": query_result.get("row_count", 0),
                }
            else:
                # (기타 카테고리 처리 로직은 기존과 동일하게 유지)
                yield create_sse_event('progress', {'stage': 'response_generation', 'message': '💬 응답 생성 중...'})
                response_data = llm_client.generate_out_of_scope(message)
                result = {"type": "out_of_scope_result", "content": response_data.get("response", "")}

            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            
            # 4. AI 응답 메시지 저장
            ai_response_content = result.get('content') or json.dumps(result.get('data', 'No content'), ensure_ascii=False)
            ai_message_data = {
                'conversation_id': conversation_id,
                'message_id': f"{conversation_id}_assistant_{int(time.time())}",
                'user_id': user_info['user_id'],
                'message': ai_response_content,
                'message_type': 'assistant',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'generated_sql': generated_sql,
                'query_id': query_id  # 쿼리 ID 연결
            }
            bigquery_client.save_conversation(ai_message_data)

            # 5. 최종 결과 전송
            yield create_sse_event('progress', {'stage': 'completed', 'message': '✅ 완료!'})
            yield create_sse_event('result', {
                'success': True,
                'request_id': request_id,
                'conversation_id': conversation_id,
                'result': result,
                'performance': {'execution_time_ms': execution_time_ms}
            })
            
            logger.info(f"✅ [{request_id}] Streaming complete ({execution_time_ms}ms)")

        except Exception as e:
            logger.error(f"❌ [{request_id}] Streaming error: {str(e)}")
            yield create_sse_event('error', {'error': f'Server error: {str(e)}', 'error_type': 'internal_error'})

    return Response(generate_stream(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})

@chat_bp.route('/conversations', methods=['GET'])
@require_auth
def get_user_conversations():
    """인증된 사용자의 대화 히스토리 목록 조회"""
    try:
        user_id = g.current_user['user_id']
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        conversations_result = bigquery_client.get_user_conversations(user_id, limit, offset)
        
        if not conversations_result['success']:
            return jsonify(ErrorResponse.service_error(
                conversations_result['error'], "bigquery"
            )), 500
        
        return jsonify({
            "success": True,
            "conversations": conversations_result['conversations'],
            "count": conversations_result['count']
        })
        
    except Exception as e:
        logger.error(f"❌ 대화 히스토리 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"대화 히스토리 조회 실패: {str(e)}")), 500

@chat_bp.route('/conversations/latest', methods=['GET'])
@require_auth
def get_latest_conversation():
    """가장 최근 대화의 모든 정보를 한 번에 반환하는 최적화된 API"""
    try:
        user_id = g.current_user['user_id']
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)

        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client not initialized", "bigquery")), 500

        # 이제 이 함수는 모든 대화를 가져옵니다.
        all_conv_result = bigquery_client.get_latest_conversation(user_id)

        if not all_conv_result.get('success'):
            return jsonify(ErrorResponse.service_error(all_conv_result.get('error', 'Unknown error'), "bigquery")), 500
        
        # 대화가 없는 경우의 응답
        if all_conv_result.get('reason') == 'not_found' or not all_conv_result.get('conversation'):
            return jsonify({"success": True, "conversation": None, "message": "No conversations found."})
            
        return jsonify(all_conv_result)
        
    except Exception as e:
        logger.error(f"❌ 전체 대화 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"전체 대화 조회 실패: {str(e)}")), 500

@chat_bp.route('/conversations/<conversation_id>', methods=['GET'])
@require_auth
def get_conversation_details(conversation_id):
    """특정 대화 세션의 상세 내역 조회"""
    try:
        user_id = g.current_user['user_id']
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        details_result = bigquery_client.get_conversation_details(conversation_id, user_id)
        
        if not details_result['success']:
             return jsonify(ErrorResponse.not_found_error(
                details_result.get('error', '대화를 찾을 수 없습니다.')
            )), 404

        if details_result['message_count'] == 0:
            return jsonify(ErrorResponse.not_found_error("대화를 찾을 수 없거나 접근 권한이 없습니다")), 404

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "messages": details_result['messages'],
            "message_count": details_result['message_count']
        })
        
    except Exception as e:
        logger.error(f"❌ 대화 상세 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"대화 상세 조회 실패: {str(e)}")), 500