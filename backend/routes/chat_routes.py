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
from features.query_processing.services import QueryProcessingService
from features.query_processing.models import QueryRequest, QueryResult
from features.input_classification.services import InputClassificationService
from features.data_analysis.services import AnalysisService
from features.data_analysis.models import AnalysisRequest
from models import ContextBlock, BlockType

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
            
            # 컨텍스트 로드 로직
            context_blocks = []
            try:
                context_result = bigquery_client.get_conversation_with_context(user_info['user_id'], limit=5)
                if context_result['success'] and 'context_blocks' in context_result:
                    context_blocks = list(reversed(context_result['context_blocks']))
                    logger.info(f"📚 [{request_id}] 컨텍스트 로드: {len(context_blocks)}개 블록")
            except Exception as e:
                logger.error(f"❌ [{request_id}] 컨텍스트 로드 중 오류: {str(e)}")
                context_blocks = []

            # 1. 입력 분류 (InputClassificationService 사용)
            yield create_sse_event('progress', {'stage': 'classification', 'message': '🔍 입력 분류 중...'})
            classification_service = InputClassificationService(llm_client)
            
            # ContextBlock을 직접 분류 서비스에 전달
            category = classification_service.classify(message, context_blocks)
            logger.info(f"🏷️ [{request_id}] Classified as: {category}")
            
            generated_sql = None
            
            # 2. 분류에 따른 처리 → Query Processing Service로 교체 (ContextBlock 사용)
            query_service = QueryProcessingService(llm_client, bigquery_client)
            
            # 현재 요청용 ContextBlock 생성
            from datetime import datetime, timezone
            
            current_context_block = ContextBlock(
                block_id=str(uuid.uuid4()),
                user_id=user_info['user_id'],
                timestamp=datetime.now(timezone.utc),
                block_type=BlockType.QUERY,  # 기본값, 나중에 분류에 따라 변경됨
                user_request=message,  # 단순 문자열
                assistant_response="",  # 빈 문자열
                status="pending"
            )
            
            request_obj = QueryRequest(
                user_id=user_info['user_id'],
                query=message,
                context_block=current_context_block
            )
            
            # 분류에 따른 진행 상태 표시 및 처리
            if category == "query_request":
                yield create_sse_event('progress', {'stage': 'sql_generation', 'message': '📝 SQL 생성 중...'})
                yield create_sse_event('progress', {'stage': 'query_execution', 'message': '⚡ 쿼리 실행 중...'})
                
                # SQL 쿼리 처리 (이전 context_blocks 전달)
                query_result = query_service.process_sql_query(request_obj, context_blocks)
                
            elif category == "data_analysis":
                yield create_sse_event('progress', {'stage': 'analysis', 'message': '📊 데이터 분석 중...'})
                
                # AnalysisService로 데이터 분석 처리
                analysis_service = AnalysisService(llm_client, bigquery_client)
                analysis_request = AnalysisRequest(
                    user_id=user_info['user_id'],
                    query=message,
                    context_block=current_context_block,
                    context_blocks=context_blocks
                )
                
                analysis_result = analysis_service.process_analysis(analysis_request)
                
                # QueryResult로 변환 (chat_routes.py의 기존 응답 형식 유지)
                query_result = QueryResult(
                    success=analysis_result.success,
                    result_type="analysis_result",
                    context_block=analysis_result.context_block,
                    content=analysis_result.analysis_content,
                    error=analysis_result.error
                )
                
            else:
                yield create_sse_event('progress', {'stage': 'response_generation', 'message': '💬 응답 생성 중...'})
                
                # TODO: 향후 ResponseService 구현 시 사용
                # response_service = ResponseService(llm_client)
                # query_result = response_service.process_response(request_obj)
                
                # 임시: 범위 외 응답
                content = "죄송합니다. 해당 질문은 현재 지원하지 않는 범위입니다."
                current_context_block.assistant_response = content
                current_context_block.status = "completed"
                
                query_result = QueryResult(
                    success=True,
                    result_type="out_of_scope_result",
                    context_block=current_context_block,
                    content=content
                )
            
            if not query_result.success:
                raise ValueError(f"Query processing failed: {query_result.error}")
            
            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            
            # AI 응답 내용은 ContextBlock에서 직접 가져오기
            ai_response_content = query_result.context_block.assistant_response if query_result.context_block else ""
            
            # 생성된 SQL 추출 (저장용)
            generated_sql = query_result.generated_sql if query_result.result_type == "query_result" else None
            
            # 통합 저장: 질문-답변-결과를 한 번에 저장
            # ContextBlock.execution_result는 이미 딕셔너리이므로 그대로 사용
            execution_result = None
            if (query_result.result_type == "query_result" and 
                query_result.context_block and 
                query_result.context_block.execution_result):
                execution_result = query_result.context_block.execution_result
            
            save_result = bigquery_client.save_complete_interaction(
                user_id=user_info['user_id'],
                user_question=message,
                assistant_answer=ai_response_content,
                generated_sql=generated_sql,
                query_result=execution_result,
                context_message_ids=[]  # 향후 확장 가능
            )
            
            if not save_result['success']:
                logger.warning(f"⚠️ [{request_id}] 통합 상호작용 저장 실패: {save_result.get('error')}")

            # 4. 최종 결과 전송
            yield create_sse_event('progress', {'stage': 'completed', 'message': '✅ 완료!'})
            
            # 클라이언트용 결과 구성
            client_result = {
                "type": query_result.result_type,
                "block_id": query_result.context_block.block_id if query_result.context_block else None
            }
            
            if query_result.result_type == "query_result":
                client_result.update({
                    "generated_sql": query_result.generated_sql,
                    "data": query_result.data,
                    "row_count": query_result.row_count
                })
            else:
                client_result["content"] = query_result.content
            
            yield create_sse_event('result', {
                'success': True,
                'request_id': request_id,
                'result': client_result,
                'performance': {'execution_time_ms': execution_time_ms}
            })
            
            logger.info(f"✅ [{request_id}] Streaming complete ({execution_time_ms}ms)")

        except Exception as e:
            logger.error(f"❌ [{request_id}] Streaming error: {str(e)}")
            yield create_sse_event('error', {'error': f'Server error: {str(e)}', 'error_type': 'internal_error'})

    return Response(generate_stream(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


@chat_bp.route('/conversations/latest', methods=['GET'])
@require_auth
def get_latest_conversation():
    """최근 대화 기록을 ContextBlock 기반으로 조회하여 프론트엔드 형식으로 반환"""
    try:
        user_id = g.current_user['user_id']
        from flask import current_app
        bigquery_client = getattr(current_app, 'bigquery_client', None)

        if not bigquery_client:
            return jsonify(ErrorResponse.service_error("BigQuery client not initialized", "bigquery")), 500

        # ContextBlock 기반 최신 대화 조회
        context_result = bigquery_client.get_conversation_with_context(user_id, 50)  # 최근 50개 조회

        if not context_result.get('success'):
            logger.warning(f"대화 조회 실패 (테이블 없을 수 있음): {context_result.get('error')}")
            return jsonify({"success": True, "conversation": {"messages": [], "message_count": 0}})
        
        # 대화가 없는 경우의 응답
        if not context_result.get('context_blocks') or len(context_result['context_blocks']) == 0:
            return jsonify({"success": True, "conversation": {"messages": [], "message_count": 0}})
            
        # ContextBlock을 프론트엔드 호환 형식으로 변환
        formatted_messages = []
        for context_block in context_result['context_blocks']:
            # 사용자 메시지
            if context_block.user_request:
                formatted_messages.append({
                    "message_id": f"{context_block.block_id}_user",
                    "message": context_block.user_request,
                    "message_type": "user",
                    "timestamp": context_block.timestamp.isoformat() if context_block.timestamp else None
                })
            
            # AI 응답 메시지
            if context_block.assistant_response:
                assistant_msg = {
                    "message_id": f"{context_block.block_id}_assistant", 
                    "message": context_block.assistant_response,
                    "message_type": "assistant",
                    "timestamp": context_block.timestamp.isoformat() if context_block.timestamp else None,
                    "generated_sql": context_block.execution_result.get('generated_sql') if context_block.execution_result else None,
                    "result_data": context_block.execution_result.get('data') if context_block.execution_result else None,
                    "result_row_count": context_block.execution_result.get('row_count') if context_block.execution_result else None
                }
                formatted_messages.append(assistant_msg)
        
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

