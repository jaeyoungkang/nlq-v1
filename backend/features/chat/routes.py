# backend/routes/chat_routes.py
"""
채팅 및 대화 관련 라우트 - ChatService 기반 경량화
"""

import time
import uuid
from flask import Blueprint, request, jsonify, g, Response, current_app
from utils.decorators import require_auth
from utils.error_utils import ErrorResponse, SuccessResponse
from utils.logging_utils import get_logger
from features.chat.models import ChatRequest

logger = get_logger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/api')

@chat_bp.route('/chat-stream', methods=['POST'])
@require_auth
def process_chat_stream():
    """SSE 스트리밍 채팅 엔드포인트 - ChatService 기반"""
    if not request.json:
        return jsonify(ErrorResponse.validation_error("JSON data is required")), 400
    
    message = request.json.get('message', '').strip()
    
    if not message:
        return jsonify(ErrorResponse.validation_error("Message cannot be empty")), 400

    # 애플리케이션 컨텍스트와 필요한 객체들을 미리 가져오기
    app = current_app._get_current_object()
    chat_service = getattr(app, 'chat_service', None)
    user_id = g.current_user['user_id']
    
    def generate_stream():
        start_time = time.time()
        request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Flask 애플리케이션 컨텍스트 설정
        with app.app_context():
            try:
                if not chat_service:
                    import json
                    error_data = json.dumps({'error': 'ChatService not initialized', 'error_type': 'service_error'})
                    yield f"event: error\ndata: {error_data}\n\n"
                    return
                
                logger.info(f"🎯 [{request_id}] Processing streaming chat: {message[:50]}...")
                
                # ChatRequest 생성
                chat_request = ChatRequest(
                    user_id=user_id,
                    message=message,
                    context_limit=5
                )
                
                # ChatService를 통한 대화 처리
                for sse_event in chat_service.process_conversation(chat_request):
                    yield sse_event
            
                execution_time_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(f"✅ [{request_id}] Streaming complete ({execution_time_ms}ms)")

            except Exception as e:
                logger.error(f"❌ [{request_id}] Streaming error: {str(e)}")
                import json
                error_data = json.dumps({'error': f'Server error: {str(e)}', 'error_type': 'internal_error'})
                yield f"event: error\ndata: {error_data}\n\n"

    return Response(generate_stream(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})


@chat_bp.route('/conversations/latest', methods=['GET'])
@require_auth
def get_latest_conversation():
    """최근 대화 기록 조회 - ChatRepository 기반"""
    try:
        user_id = g.current_user['user_id']
        
        chat_repository = getattr(current_app, 'chat_repository', None)
        if not chat_repository:
            return jsonify(ErrorResponse.service_error("ChatRepository not initialized", "repository")), 500

        # 최신 대화 조회
        context_result = chat_repository.get_conversation_with_context(user_id, 50)

        if not context_result.get('success'):
            logger.warning(f"대화 조회 실패 (테이블 없을 수 있음): {context_result.get('error')}")
            return jsonify(SuccessResponse.success({"conversation": {"messages": [], "message_count": 0}}))
        
        # 대화가 없는 경우의 응답
        if not context_result.get('context_blocks') or len(context_result['context_blocks']) == 0:
            return jsonify(SuccessResponse.success({"conversation": {"messages": [], "message_count": 0}}))
            
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
                    "generated_sql": context_block.generated_query,
                    "result_data": context_block.execution_result.get('data') if context_block.execution_result else None,
                    "result_row_count": context_block.execution_result.get('row_count') if context_block.execution_result else None
                }
                formatted_messages.append(assistant_msg)
        
        return jsonify(SuccessResponse.success({
            "conversation": {
                "messages": formatted_messages,
                "message_count": len(formatted_messages)
            }
        }))
        
    except Exception as e:
        logger.error(f"❌ 전체 대화 조회 중 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"전체 대화 조회 실패: {str(e)}")), 500

