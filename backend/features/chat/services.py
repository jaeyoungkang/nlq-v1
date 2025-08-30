"""
Chat Service
대화 워크플로우 오케스트레이션 - 도메인 서비스들을 조율하여 대화 처리
"""

from typing import Dict, Any, List, Optional, Generator
import json
from datetime import datetime

from features.chat.repositories import ChatRepository
from features.chat.models import ChatRequest, ChatResponse, ChatContext, StreamEvent
from features.input_classification.services import InputClassificationService
from features.query_processing.services import QueryProcessingService
from features.data_analysis.services import AnalysisService
from core.models import ContextBlock
from utils.logging_utils import get_logger
from utils.error_utils import ErrorResponse

logger = get_logger(__name__)


class ChatService:
    """대화 워크플로우 오케스트레이션 서비스"""
    
    def __init__(
        self,
        chat_repository: ChatRepository,
        classification_service: InputClassificationService,
        query_service: QueryProcessingService,
        analysis_service: AnalysisService
    ):
        """
        ChatService 초기화
        
        Args:
            chat_repository: 대화 저장소
            classification_service: 입력 분류 서비스
            query_service: 쿼리 처리 서비스 
            analysis_service: 데이터 분석 서비스
        """
        self.chat_repository = chat_repository
        self.classification_service = classification_service
        self.query_service = query_service
        self.analysis_service = analysis_service
    
    def process_conversation(
        self, 
        request: ChatRequest
    ) -> Generator[str, None, None]:
        """
        대화 처리 워크플로우 오케스트레이션
        
        Args:
            request: 대화 요청
            
        Yields:
            SSE 형식의 스트림 이벤트
        """
        try:
            # 1. 컨텍스트 로드
            context = self.load_context(request.user_id, request.context_limit)
            yield StreamEvent(
                event="context_loaded",
                data={"message": f"컨텍스트 로드 완료 ({len(context)} 블록)"}
            ).to_sse()
            
            # 2. 입력 분류
            classification_category = self.classification_service.classify(
                request.message,
                context
            )
            
            if not classification_category:
                yield StreamEvent(
                    event="error",
                    data={"error": "분류 실패"}
                ).to_sse()
                return
            
            category = classification_category
            yield StreamEvent(
                event="classification",
                data={"category": category}
            ).to_sse()
            
            # 3. 카테고리별 처리
            result = self._process_by_category(
                category=category,
                user_input=request.message,
                user_id=request.user_id,
                context_blocks=context
            )
            
            # 4. 결과 스트리밍
            for event in self._stream_result(result, category):
                yield event
            
            # 4.5. 최종 결과 이벤트 (프론트엔드 호환)
            final_result_event = self._create_final_result_event(result, category)
            if final_result_event:
                yield final_result_event
                
            # 5. 대화 저장 (ContextBlock 기반)
            save_result = self._save_context_block(
                user_id=request.user_id,
                category=category,
                result=result
            )
            
            if save_result.get('success'):
                yield StreamEvent(
                    event="saved",
                    data={"message": "대화가 저장되었습니다"}
                ).to_sse()
            
            # 6. 완료 이벤트
            yield StreamEvent(
                event="complete",
                data={"message": "대화 처리 완료"}
            ).to_sse()
            
        except Exception as e:
            logger.error(f"대화 처리 중 오류: {str(e)}")
            yield StreamEvent(
                event="error",
                data={"error": str(e)}
            ).to_sse()
    
    def load_context(
        self, 
        user_id: str, 
        limit: int = 5
    ) -> List[ContextBlock]:
        """
        사용자 대화 컨텍스트 로드
        
        Args:
            user_id: 사용자 ID
            limit: 컨텍스트 블록 수 제한
            
        Returns:
            컨텍스트 블록 리스트
        """
        try:
            result = self.chat_repository.get_conversation_with_context(user_id, limit)
            
            if result.get('success') and result.get('context_blocks'):
                # ChatRepository는 이미 ContextBlock 객체 리스트를 반환
                return result['context_blocks']
            
            return []
            
        except Exception as e:
            logger.error(f"컨텍스트 로드 중 오류: {str(e)}")
            return []
    
    def _process_by_category(
        self,
        category: str,
        user_input: str,
        user_id: str,
        context_blocks: List[ContextBlock]
    ) -> Dict[str, Any]:
        """
        카테고리별 처리 라우팅
        
        Args:
            category: 입력 카테고리
            user_input: 사용자 입력
            user_id: 사용자 ID
            context_blocks: 컨텍스트 블록
            
        Returns:
            처리 결과
        """
        try:
            if category == "query_request":
                # QueryRequest 생성 (user_id 필수)
                from features.query_processing.models import QueryRequest
                
                query_request = QueryRequest(
                    user_id=user_id,
                    query=user_input
                )
                
                query_result = self.query_service.process_sql_query(query_request, context_blocks)
                
                # QueryResult를 ChatService 형식으로 변환
                return {
                    'success': query_result.success,
                    'category': category,
                    'message': query_result.context_block.assistant_response if query_result.context_block else '',
                    'data': query_result.data,
                    'generated_query': query_result.generated_query,
                    'context_block': query_result.context_block,
                    'error': query_result.error
                }
            
            elif category == "data_analysis":
                # AnalysisRequest 생성
                from features.data_analysis.models import AnalysisRequest
                from core.models import ContextBlock, BlockType
                import uuid
                from datetime import datetime, timezone
                
                analysis_context_block = ContextBlock(
                    block_id=str(uuid.uuid4()),
                    user_id=user_id,
                    timestamp=datetime.now(timezone.utc),
                    block_type=BlockType.ANALYSIS,
                    user_request=user_input,
                    assistant_response="",
                    execution_result=None,
                    status="pending"
                )
                
                analysis_request = AnalysisRequest(
                    user_id=user_id,
                    query=user_input,
                    context_block=analysis_context_block,
                    context_blocks=context_blocks
                )
                
                analysis_result = self.analysis_service.process_analysis(analysis_request)
                
                # AnalysisResult를 ChatService 형식으로 변환
                return {
                    'success': analysis_result.success,
                    'category': category,
                    'message': analysis_result.analysis_content,
                    'data': None,  # 분석 결과는 보통 텍스트 응답
                    'context_block': analysis_result.context_block,
                    'error': analysis_result.error
                }
            
            elif category == "metadata_request":
                return self.query_service.get_metadata_info(
                    user_input=user_input,
                    context_blocks=context_blocks
                )
            
            elif category == "guide_request":
                return {
                    'success': True,
                    'category': category,
                    'message': self._get_guide_message(),
                    'data': None
                }
            
            else:  # out_of_scope
                return {
                    'success': True,
                    'category': category,
                    'message': "죄송합니다. 해당 요청은 처리할 수 없습니다. BigQuery 데이터 조회 및 분석 관련 질문을 해주세요.",
                    'data': None
                }
                
        except Exception as e:
            logger.error(f"카테고리별 처리 중 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'category': category
            }
    
    def _stream_result(
        self,
        result: Dict[str, Any],
        category: str
    ) -> Generator[str, None, None]:
        """
        결과를 SSE 이벤트로 스트리밍
        
        Args:
            result: 처리 결과
            category: 입력 카테고리
            
        Yields:
            SSE 형식 이벤트
        """
        if not result.get('success'):
            yield StreamEvent(
                event="error",
                data={"error": result.get('error', '처리 실패')}
            ).to_sse()
            return
        
        # 메시지 스트리밍
        if result.get('message'):
            yield StreamEvent(
                event="message",
                data={"content": result['message']}
            ).to_sse()
        
        # SQL 스트리밍 (쿼리 요청인 경우)
        if category == "query_request" and result.get('generated_query'):
            yield StreamEvent(
                event="sql",
                data={"sql": result['generated_query']}
            ).to_sse()
        
        # 데이터 스트리밍
        if result.get('data'):
            yield StreamEvent(
                event="data",
                data={"results": result['data']}
            ).to_sse()
    
    def _create_final_result_event(
        self,
        result: Dict[str, Any],
        category: str
    ) -> Optional[str]:
        """
        프론트엔드 호환을 위한 최종 결과 이벤트 생성
        
        Args:
            result: 처리 결과
            category: 입력 카테고리
            
        Returns:
            SSE 형식 최종 결과 이벤트 또는 None
        """
        if not result.get('success'):
            return None
        
        # 카테고리에 따른 결과 타입 매핑
        result_type_mapping = {
            "query_request": "query_result",
            "data_analysis": "analysis_result", 
            "metadata_request": "metadata_result",
            "guide_request": "guide_result",
            "out_of_scope": "out_of_scope_result"
        }
        
        result_type = result_type_mapping.get(category, "unknown_result")
        
        # 최종 결과 구성
        final_result_data = {
            "success": True,
            "request_id": f"req_{int(__import__('time').time())}",
            "result": {
                "type": result_type,
                "content": result.get('message', ''),
                "generated_sql": result.get('generated_query'),
                "data": result.get('data'),
                "row_count": len(result['data']) if result.get('data') and isinstance(result['data'], list) else None
            },
            "performance": {
                "execution_time_ms": 0  # 실제 측정값으로 대체 필요시
            }
        }
        
        # None 값 제거
        if not final_result_data["result"]["generated_sql"]:
            del final_result_data["result"]["generated_sql"]
        if not final_result_data["result"]["data"]:
            del final_result_data["result"]["data"]
        if final_result_data["result"]["row_count"] is None:
            del final_result_data["result"]["row_count"]
        
        return StreamEvent(
            event="result",
            data=final_result_data
        ).to_sse()
    
    def _save_context_block(
        self,
        user_id: str,
        category: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ContextBlock 기반 대화 저장
        
        Args:
            user_id: 사용자 ID
            category: 입력 카테고리
            result: 처리 결과 (ContextBlock 포함)
            
        Returns:
            저장 결과
        """
        try:
            # 서비스 결과에서 ContextBlock 추출
            context_block = result.get('context_block')
            
            if not context_block:
                logger.warning("결과에 ContextBlock이 없음 - 저장 건너뜀")
                return {'success': True, 'message': 'ContextBlock 없음으로 저장 건너뜀'}
            
            # ContextBlock을 직접 저장
            return self._save_context_block_direct(context_block)
            
        except Exception as e:
            logger.error(f"ContextBlock 저장 중 오류: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _save_context_block_direct(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock을 직접 BigQuery에 저장"""
        try:
            # ChatRepository의 save_context_block 메서드 사용
            return self.chat_repository.save_context_block(context_block)
                
        except Exception as e:
            logger.error(f"ContextBlock 직접 저장 중 오류: {str(e)}")
            return {'success': False, 'error': f'ContextBlock 저장 실패: {str(e)}'}
    
    def _get_guide_message(self) -> str:
        """가이드 메시지 반환"""
        return """
Analytics Assistant AI 사용 가이드:

**사용 가능한 기능:**
1. **데이터 조회**: "지난달 매출은?", "어제 사용자 수 조회"
2. **데이터 분석**: "매출 추이 분석", "사용자 행동 패턴 분석"
3. **메타데이터 조회**: "테이블 구조 보여줘", "컬럼 정보 확인"

**팁:**
- 구체적인 기간과 지표를 명시하면 더 정확한 결과를 얻을 수 있습니다
- 이전 대화 내용을 참조하여 연속적인 질문이 가능합니다
- SQL을 직접 확인하고 수정을 요청할 수 있습니다
"""