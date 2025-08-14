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
            
            # 컨텍스트 로드 로직 - user_id 기반으로 변경
            conversation_context = []
            try:
                context_result = bigquery_client.get_conversation_context(user_info['user_id'], max_messages=5)
                if context_result['success']:
                    conversation_context = context_result['context']
                    logger.info(f"📚 [{request_id}] 컨텍스트 로드: {len(conversation_context)}개 메시지")
                else:
                    logger.warning(f"⚠️ [{request_id}] 컨텍스트 로드 실패: {context_result.get('error')}")
            except Exception as e:
                logger.error(f"❌ [{request_id}] 컨텍스트 로드 중 오류: {str(e)}")
                conversation_context = []

            # 1. 사용자 메시지 저장
            user_message_data = {
                'message_id': f"{user_info['user_id']}_user_{int(time.time())}",
                'user_id': user_info['user_id'],
                'message': message,
                'message_type': 'user',
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            bigquery_client.save_conversation(user_message_data)

            # 2. 입력 분류
            yield create_sse_event('progress', {'stage': 'classification', 'message': '🔍 입력 분류 중...'})
            logger.info(f"🔍 [{request_id}] 분류 시 컨텍스트 전달: len={len(conversation_context)}")
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
            elif category == "data_analysis":
                # 데이터 분석 요청 처리
                yield create_sse_event('progress', {'stage': 'analysis', 'message': '📊 데이터 분석 중...'})
                
                # 컨텍스트에서 이전 SQL과 데이터 추출
                previous_sql = None
                previous_data = None
                
                if conversation_context:
                    for ctx_msg in reversed(conversation_context):
                        # 컨텍스트에 쿼리 결과가 직접 포함되어 있는지 확인
                        if ctx_msg.get('query_result_data') and ctx_msg.get('metadata', {}).get('generated_sql'):
                            previous_sql = ctx_msg['metadata']['generated_sql']
                            previous_data = ctx_msg['query_result_data']
                            logger.info(f"📊 [{request_id}] 컨텍스트에서 이전 쿼리 결과 로드: {len(previous_data)}행")
                            break
                
                analysis_result = llm_client.analyze_data(message, previous_data, previous_sql, conversation_context)
                if analysis_result.get("success"):
                    result = {"type": "analysis_result", "content": analysis_result.get("analysis", "")}
                else:
                    result = {"type": "analysis_result", "content": "분석 중 오류가 발생했습니다."}
            else:
                # 기타 카테고리 처리
                yield create_sse_event('progress', {'stage': 'response_generation', 'message': '💬 응답 생성 중...'})
                response_data = llm_client.generate_out_of_scope(message)
                result = {"type": "out_of_scope_result", "content": response_data.get("response", "")}

            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            
            # 4. AI 응답 메시지 저장
            ai_response_content = ""
            if result.get("type") == "query_result":
                row_count = result.get("row_count", 0)
                ai_response_content = f"📊 조회 결과: {row_count}개의 행이 반환되었습니다."
            else:
                ai_response_content = result.get('content')
            
            ai_message_data = {
                'message_id': f"{user_info['user_id']}_assistant_{int(time.time())}",
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

