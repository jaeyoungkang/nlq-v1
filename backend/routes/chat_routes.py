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
            
            # 컨텍스트 로드 로직 - 통합 구조 사용
            conversation_context = []
            try:
                context_result = bigquery_client.get_conversation_with_context(user_info['user_id'], limit=5)
                if context_result['success']:
                    # 계획서 기준 - 별도 필드 직접 사용
                    conversations = context_result['conversations']
                    for conv in reversed(conversations):  # 시간순 정렬
                        # 사용자 메시지 추가 (별도 필드에서 직접)
                        if conv.get('user_question'):
                            conversation_context.append({
                                "role": "user",
                                "content": conv['user_question'],
                                "timestamp": conv['timestamp']
                            })
                        
                        # AI 응답 메시지 추가 (별도 필드에서 직접)
                        if conv.get('assistant_answer'):
                            ai_msg = {
                                "role": "assistant", 
                                "content": conv['assistant_answer'],
                                "timestamp": conv['timestamp'],
                                "metadata": {"generated_sql": conv.get('generated_sql')}
                            }
                            
                            # 쿼리 결과 포함
                            if conv.get('result_data'):
                                ai_msg['query_result_data'] = conv['result_data']
                                ai_msg['query_row_count'] = conv.get('result_row_count', 0)
                            
                            conversation_context.append(ai_msg)
                    
                    logger.info(f"📚 [{request_id}] 컨텍스트 로드: {len(conversation_context)}개 메시지")
                else:
                    logger.warning(f"⚠️ [{request_id}] 컨텍스트 로드 실패: {context_result.get('error')}")
            except Exception as e:
                logger.error(f"❌ [{request_id}] 컨텍스트 로드 중 오류: {str(e)}")
                conversation_context = []


            # 1. 입력 분류
            yield create_sse_event('progress', {'stage': 'classification', 'message': '🔍 입력 분류 중...'})
            classification_result = llm_client.classify_input(message, conversation_context)
            category = classification_result.get("classification", {}).get("category", "query_request")
            logger.info(f"🏷️ [{request_id}] Classified as: {category}")
            
            result = {}
            generated_sql = None
            query_id = None
            
            # 2. 분류에 따른 처리
            if category == "query_request":
                yield create_sse_event('progress', {'stage': 'sql_generation', 'message': '📝 SQL 생성 중...'})
                sql_result = llm_client.generate_sql(message, bigquery_client.project_id, None, conversation_context)
                if not sql_result["success"]:
                    raise ValueError(f"SQL generation failed: {sql_result.get('error')}")
                
                generated_sql = sql_result["sql"]
                query_id = str(uuid.uuid4()) # 쿼리 ID 생성
                
                yield create_sse_event('progress', {'stage': 'query_execution', 'message': '⚡ 쿼리 실행 중...'})
                query_result = bigquery_client.execute_query(generated_sql)

                result = {
                    "type": "query_result",
                    "generated_sql": generated_sql,
                    "data": query_result.get("data", []),
                    "row_count": query_result.get("row_count", 0),
                }
            elif category == "data_analysis":
                # 데이터 분석 요청 처리
                yield create_sse_event('progress', {'stage': 'analysis', 'message': '📊 데이터 분석 중...'})
                
                # LLM이 컨텍스트에서 직접 쿼리 결과를 추출하여 분석
                analysis_result = llm_client.analyze_data(
                    message, 
                    None,  # previous_data 제거 (컨텍스트에서 추출)
                    None,  # previous_sql 제거 (컨텍스트에서 추출)
                    conversation_context  # 전체 대화 컨텍스트만 전달
                )
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
            
            # 3. 통합 저장 방식으로 전체 상호작용 저장
            ai_response_content = ""
            if result.get("type") == "query_result":
                row_count = result.get("row_count", 0)
                ai_response_content = f"📊 조회 결과: {row_count}개의 행이 반환되었습니다."
            else:
                ai_response_content = result.get('content', '')
            
            # 통합 저장: 질문-답변-결과를 한 번에 저장
            save_result = bigquery_client.save_complete_interaction(
                user_id=user_info['user_id'],
                user_question=message,
                assistant_answer=ai_response_content,
                generated_sql=generated_sql,
                query_result=query_result if result.get("type") == "query_result" else None,
                context_message_ids=[]  # 향후 확장 가능
            )
            
            if not save_result['success']:
                logger.warning(f"⚠️ [{request_id}] 통합 상호작용 저장 실패: {save_result.get('error')}")

            # 4. 최종 결과 전송
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
        
        conversations_result = bigquery_client.get_conversation_with_context(user_id, limit)
        
        if not conversations_result['success']:
            return jsonify(ErrorResponse.service_error(
                conversations_result['error'], "bigquery"
            )), 500
        
        # 프론트엔드 호환 형식으로 변환
        formatted_conversations = []
        for conv in conversations_result['conversations']:
            # 사용자 질문과 AI 답변을 별도 메시지로 분리
            if conv.get('user_question'):
                formatted_conversations.append({
                    "message_id": f"{conv['message_id']}_user",
                    "message": conv['user_question'],
                    "message_type": "user", 
                    "timestamp": conv['timestamp']
                })
            
            if conv.get('assistant_answer'):
                formatted_conversations.append({
                    "message_id": f"{conv['message_id']}_assistant",
                    "message": conv['assistant_answer'],
                    "message_type": "assistant",
                    "timestamp": conv['timestamp'],
                    "generated_sql": conv.get('generated_sql'),
                    "result_data": conv.get('result_data'),
                    "result_row_count": conv.get('result_row_count')
                })
        
        return jsonify({
            "success": True,
            "conversations": formatted_conversations,
            "count": len(formatted_conversations)
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

        # 통합된 구조로 최신 대화 조회
        all_conv_result = bigquery_client.get_conversation_with_context(user_id, 50)  # 최근 50개 조회

        if not all_conv_result.get('success'):
            # 테이블이 없거나 다른 에러가 있어도 빈 결과 반환
            logger.warning(f"대화 조회 실패 (테이블 없을 수 있음): {all_conv_result.get('error')}")
            return jsonify({"success": True, "conversations": [], "message": "No conversations found."})
        
        # 대화가 없는 경우의 응답
        if not all_conv_result.get('conversations') or len(all_conv_result['conversations']) == 0:
            return jsonify({"success": True, "conversations": [], "message": "No conversations found."})
            
        # conversations를 프론트엔드 호환 형식으로 변환
        formatted_messages = []
        for conv in all_conv_result['conversations']:
            # 사용자 질문과 AI 답변을 별도 메시지로 분리
            if conv.get('user_question'):
                formatted_messages.append({
                    "message_id": f"{conv['message_id']}_user",
                    "message": conv['user_question'],
                    "message_type": "user",
                    "timestamp": conv['timestamp']
                })
            
            if conv.get('assistant_answer'):
                formatted_messages.append({
                    "message_id": f"{conv['message_id']}_assistant", 
                    "message": conv['assistant_answer'],
                    "message_type": "assistant",
                    "timestamp": conv['timestamp'],
                    "generated_sql": conv.get('generated_sql'),
                    "result_data": conv.get('result_data'),
                    "result_row_count": conv.get('result_row_count')
                })
        
        return jsonify({
            "success": True,
            "conversation": {
                "messages": formatted_messages,
                "message_count": len(formatted_messages)
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 전체 대화 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"전체 대화 조회 실패: {str(e)}")), 500

