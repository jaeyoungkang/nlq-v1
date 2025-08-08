"""
채팅 및 대화 관련 라우트
AI 채팅, SQL 검증, 대화 관리 등 - 로그인 필수 버전 (SSE 스트리밍 추가)
"""

import os
import time
import json
import logging
import datetime
from flask import Blueprint, request, jsonify, g, Response
from utils.auth_utils import require_auth

logger = logging.getLogger(__name__)

# 블루프린트 생성
chat_bp = Blueprint('chat', __name__, url_prefix='/api')

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


def create_sse_event(event_type: str, data: dict) -> str:
    """SSE 이벤트 형식으로 데이터 생성 (개행 문자 추가)"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@chat_bp.route('/chat-stream', methods=['POST'])
@require_auth
def process_chat_stream():
    """
    SSE 스트리밍 채팅 엔드포인트 (인증된 사용자 전용)
    """
    if not request.json:
        return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
    
    message = request.json.get('message', '').strip()
    conversation_id = request.json.get('conversation_id', f"conv_{int(time.time())}_{id(request)}")
    
    if not message:
        return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400

    def generate_stream():
        start_time = time.time()
        request_id = f"req_{int(time.time())}_{id(request)}"
        
        try:
            # LLM 클라이언트 가져오기
            from flask import current_app
            llm_client = getattr(current_app, 'llm_client', None)
            bigquery_client = getattr(current_app, 'bigquery_client', None)
            
            if not llm_client:
                yield create_sse_event('error', {
                    'error': 'LLM client is not initialized',
                    'error_type': 'service_error'
                })
                return
            
            logger.info(f"🎯 [{request_id}] Processing streaming chat: {message[:50]}...")
            
            # 인증된 사용자 정보 수집
            user_info = {
                'user_id': g.current_user['user_id'],
                'user_email': g.current_user['email'],
                'ip_address': request.remote_addr or 'unknown',
                'user_agent': request.headers.get('User-Agent', '')
            }
            
            # 1단계: 입력 분류
            progress_event = create_sse_event('progress', {
                'stage': 'classification',
                'message': '🔍 입력 분류 중...'
            })
            yield progress_event
            
            # 즉시 전송 보장을 위한 플러시 이벤트
            yield "data: \n\n"
            
            classification_result = llm_client.classify_input(message)
            if not classification_result["success"]:
                category = "query_request"
            else:
                category = classification_result["classification"]["category"]
            
            logger.info(f"🏷️ [{request_id}] Classified as: {category}")
            
            result = {}
            generated_sql = None
            
            # 2단계: 분류 결과에 따른 기능 실행
            if category == "query_request":
                if not bigquery_client:
                    yield create_sse_event('error', {
                        'error': 'BigQuery client is not initialized',
                        'error_type': 'service_error'
                    })
                    return
                
                progress_event = create_sse_event('progress', {
                    'stage': 'sql_generation',
                    'message': '📝 SQL 생성 중...'
                })
                yield progress_event
                yield "data: \n\n"  # 즉시 전송 보장
                
                sql_result = llm_client.generate_sql(message, bigquery_client.project_id)
                if not sql_result["success"]:
                    yield create_sse_event('error', {
                        'error': f'SQL generation failed: {sql_result["error"]}',
                        'error_type': 'sql_generation_error'
                    })
                    return
                
                generated_sql = sql_result["sql"]
                
                yield create_sse_event('progress', {
                    'stage': 'query_execution',
                    'message': '⚡ 쿼리 실행 중...'
                })
                
                query_result = bigquery_client.execute_query(generated_sql)
                
                if not query_result["success"]:
                    yield create_sse_event('error', {
                        'error': f'Query execution failed: {query_result["error"]}',
                        'error_type': 'query_execution_error'
                    })
                    return

                result = {
                    "type": "query_result",
                    "generated_sql": generated_sql,
                    "data": query_result["data"],
                    "row_count": query_result["row_count"],
                }
            
            elif category == "metadata_request":
                if not bigquery_client:
                    yield create_sse_event('error', {
                        'error': 'BigQuery client is not initialized',
                        'error_type': 'service_error'
                    })
                    return
                
                yield create_sse_event('progress', {
                    'stage': 'metadata_processing',
                    'message': '📋 메타데이터 조회 중...'
                })
                
                metadata = bigquery_client.get_default_table_metadata()
                response_data = llm_client.generate_metadata_response(message, metadata)
                result = {"type": "metadata_result", "content": response_data.get("response", "")}

            elif category == "data_analysis":
                yield create_sse_event('progress', {
                    'stage': 'data_analysis',
                    'message': '🤖 데이터 분석 중...'
                })
                
                response_data = llm_client.analyze_data(message)
                result = {"type": "analysis_result", "content": response_data.get("analysis", "")}

            elif category == "guide_request":
                yield create_sse_event('progress', {
                    'stage': 'guide_generation',
                    'message': '💡 가이드 생성 중...'
                })
                
                response_data = llm_client.generate_guide(message)
                result = {"type": "guide_result", "content": response_data.get("guide", "")}
                
            else: # out_of_scope
                yield create_sse_event('progress', {
                    'stage': 'response_generation',
                    'message': '💬 응답 생성 중...'
                })
                
                response_data = llm_client.generate_out_of_scope(message)
                result = {"type": "out_of_scope_result", "content": response_data.get("response", "")}

            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            
            # 완료 단계
            yield create_sse_event('progress', {
                'stage': 'completed',
                'message': '✅ 완료!'
            })
            
            # 3단계: 대화 저장 (BigQuery)
            conversation_saved = False
            if bigquery_client:
                try:
                    # 사용자 메시지 저장
                    user_message_data = {
                        'conversation_id': conversation_id,
                        'message_id': f"{conversation_id}_user_{int(time.time())}",
                        'user_id': user_info['user_id'],
                        'user_email': user_info['user_email'],
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
                    
                    logger.info(f"💾 [{request_id}] Saving conversation for user: {user_info['user_id']}")
                    
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
            
            # 최종 결과 전송
            yield create_sse_event('result', {
                'success': True,
                'request_id': request_id,
                'conversation_id': conversation_id,
                'result': result,
                'performance': {'execution_time_ms': execution_time_ms},
                'conversation_saved': conversation_saved,
                'user': {
                    'user_id': user_info['user_id'],
                    'email': user_info['user_email']
                }
            })
            
            logger.info(f"✅ [{request_id}] Streaming complete ({execution_time_ms}ms)")
            
        except Exception as e:
            logger.error(f"❌ [{request_id}] Streaming error: {str(e)}")
            yield create_sse_event('error', {
                'error': f'Server error: {str(e)}',
                'error_type': 'internal_error'
            })

    return Response(
        generate_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control',
            'X-Accel-Buffering': 'no'  # Nginx 버퍼링 비활성화
        }
    )


@chat_bp.route('/chat', methods=['POST'])
@require_auth
def process_chat():
    """
    통합 채팅 엔드포인트 (인증된 사용자 전용) - 기존 기능 유지
    """
    start_time = time.time()
    request_id = f"req_{int(time.time())}_{id(request)}"
    
    try:
        if not request.json:
            return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
        
        message = request.json.get('message', '').strip()
        conversation_id = request.json.get('conversation_id', f"conv_{int(time.time())}_{id(request)}")
        
        if not message:
            return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400
        
        # LLM 클라이언트 가져오기
        from flask import current_app
        llm_client = getattr(current_app, 'llm_client', None)
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not llm_client:
            return jsonify(ErrorResponse.service_error("LLM client is not initialized", "llm")), 500
        
        logger.info(f"🎯 [{request_id}] Processing chat message: {message[:50]}...")
        
        # 인증된 사용자 정보 수집
        user_info = {
            'user_id': g.current_user['user_id'],
            'user_email': g.current_user['email'],
            'ip_address': request.remote_addr or 'unknown',
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        # 1. 사용자 입력 분류
        classification_result = llm_client.classify_input(message)
        if not classification_result["success"]:
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
            
            # 쿼리 결과를 별도 테이블에 저장 (assistant 메시지 ID는 나중에 생성)
            query_result_to_save = {
                "conversation_id": conversation_id,
                "user_id": user_info['user_id'],
                "generated_sql": generated_sql,
                "result_data": query_result["data"],
                "row_count": query_result["row_count"]
            }
        
        elif category == "metadata_request":
            if not bigquery_client:
                 raise ValueError("BigQuery client is not initialized")
            metadata = bigquery_client.get_default_table_metadata()
            response_data = llm_client.generate_metadata_response(message, metadata)
            result = {"type": "metadata_result", "content": response_data.get("response", "")}

        elif category == "data_analysis":
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
                
                logger.info(f"💾 [{request_id}] Saving conversation for user: {user_info['user_id']}")
                
                # BigQuery에 저장
                save_user_msg = bigquery_client.save_conversation(user_message_data)
                save_ai_msg = bigquery_client.save_conversation(ai_message_data)
                
                # 쿼리 결과가 있는 경우 별도 테이블에 저장
                if category == "query_request" and 'query_result_to_save' in locals():
                    query_result_to_save['message_id'] = ai_message_data['message_id']
                    query_result_to_save['execution_time_ms'] = execution_time_ms
                    
                    query_save_result = bigquery_client.save_query_result(query_result_to_save)
                    if query_save_result['success']:
                        logger.info(f"📊 [{request_id}] 쿼리 결과 저장 완료: {query_save_result['data_size_bytes']:,} bytes")
                    else:
                        logger.warning(f"⚠️ [{request_id}] 쿼리 결과 저장 실패: {query_save_result['error']}")
                
                conversation_saved = save_user_msg['success'] and save_ai_msg['success']
                
                if not conversation_saved:
                    # 저장 실패 상세 정보 로깅
                    user_error = save_user_msg.get('error', 'Unknown') if not save_user_msg['success'] else 'OK'
                    ai_error = save_ai_msg.get('error', 'Unknown') if not save_ai_msg['success'] else 'OK'
                    logger.warning(f"⚠️ [{request_id}] 대화 저장 실패 - User: {user_error}, AI: {ai_error}")
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
            "conversation_saved": conversation_saved,
            "user": {
                "user_id": user_info['user_id'],
                "email": user_info['user_email']
            }
        }
        
        logger.info(f"✅ [{request_id}] Processing complete ({execution_time_ms}ms)")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ [{getattr(locals(), 'request_id', 'unknown')}] Chat processing exception: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"Server error: {str(e)}")), 500


@chat_bp.route('/validate-sql', methods=['POST'])
@require_auth
def validate_sql():
    """
    SQL 쿼리 문법 검증 (인증된 사용자 전용)
    """
    try:
        if not request.json or 'sql' not in request.json:
            return jsonify(ErrorResponse.validation_error("SQL query is required")), 400
        
        sql_query = request.json['sql'].strip()
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client is not initialized", "bigquery")), 500
        
        validation_result = bigquery_client.validate_query(sql_query)
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"❌ SQL validation error: {str(e)}")
        return jsonify(ErrorResponse.service_error(f"Validation error: {str(e)}", "bigquery")), 500


@chat_bp.route('/conversations', methods=['GET'])
@require_auth
def get_user_conversations():
    """
    인증된 사용자의 대화 히스토리 목록 조회
    """
    try:
        user_id = g.current_user['user_id']
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
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


@chat_bp.route('/conversations/<conversation_id>', methods=['GET'])
@require_auth
def get_conversation_details(conversation_id):
    """
    특정 대화 세션의 상세 내역 조회
    """
    try:
        user_id = g.current_user['user_id']
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
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


@chat_bp.route('/conversations/<conversation_id>', methods=['DELETE'])
@require_auth
def delete_conversation(conversation_id):
    """
    특정 대화 세션 삭제
    """
    try:
        user_id = g.current_user['user_id']
        
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)
        
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