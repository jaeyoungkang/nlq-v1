"""
Chat Repository
대화 관련 데이터 접근 계층 - ContextBlock 중심 Firestore 구현
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from google.cloud import firestore
from core.repositories.firestore_base import FirestoreRepository
from core.models import ContextBlock, BlockType
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class ChatRepository(FirestoreRepository):
    """
    대화 관련 데이터 접근 계층 (Firestore 구현)
    ContextBlock 중심의 단순화된 설계
    """
    
    def __init__(self, project_id: Optional[str] = None):
        # users 컬렉션을 기본으로 사용 (서브컬렉션으로 conversations 관리)
        super().__init__(collection_name="users", project_id=project_id)
    
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """
        ContextBlock을 Firestore에 저장 (이메일 기반)
        사용자별 conversations 서브컬렉션에 저장
        """
        try:
            # ContextBlock을 딕셔너리로 변환
            block_data = context_block.to_dict()
            
            # 사용자별 conversations 서브컬렉션에 저장 (이메일을 user_id로 사용)
            user_ref = self.client.collection("users").document(context_block.user_id)
            conversations_ref = user_ref.collection("conversations")
            
            # block_id를 문서 ID로 사용하여 저장
            conversations_ref.document(context_block.block_id).set(block_data)
            
            logger.info(f"ContextBlock 저장 완료: user={context_block.user_id}, block={context_block.block_id}")
            return {
                "success": True, 
                "block_id": context_block.block_id,
                "message": "ContextBlock이 성공적으로 저장되었습니다"
            }
            
        except Exception as e:
            logger.error(f"ContextBlock 저장 중 오류: {str(e)}")
            return {"success": False, "error": f"ContextBlock 저장 실패: {str(e)}"}
        
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        사용자의 대화 기록을 ContextBlock 리스트로 조회 (이메일 기반)
        BaseRepository 인터페이스 구현 - user_id는 이메일 주소
        """
        try:
            # 사용자별 conversations 서브컬렉션에서 조회 (user_id = 이메일)
            user_ref = self.client.collection("users").document(user_id)
            conversations_ref = user_ref.collection("conversations")
            
            # timestamp 기준 내림차순으로 정렬하여 최근 대화부터 조회
            query = conversations_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
            
            docs = query.stream()
            context_blocks = []
            
            for doc in docs:
                try:
                    doc_data = doc.to_dict()
                    
                    # Firestore Timestamp를 datetime으로 변환
                    timestamp = doc_data.get('timestamp')
                    if timestamp and hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                    elif isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    # BlockType enum 변환
                    block_type_str = doc_data.get('block_type', 'QUERY')
                    block_type = BlockType(block_type_str) if block_type_str else BlockType.QUERY
                    
                    context_block = ContextBlock(
                        block_id=doc_data.get('block_id', ''),
                        user_id=doc_data.get('user_id', user_id),  # user_id = 이메일
                        timestamp=timestamp or datetime.now(timezone.utc),
                        block_type=block_type,
                        user_request=doc_data.get('user_request', ''),
                        assistant_response=doc_data.get('assistant_response', ''),
                        generated_query=doc_data.get('generated_query'),
                        execution_result=doc_data.get('execution_result'),
                        status=doc_data.get('status', 'completed')
                    )
                    context_blocks.append(context_block)
                    
                except Exception as doc_error:
                    logger.warning(f"문서 처리 중 오류 (건너뜀): {str(doc_error)}")
                    continue
            
            logger.info(f"대화 컨텍스트 조회 완료: user={user_id}, {len(context_blocks)}개 블록")
            return {'success': True, 'context_blocks': context_blocks}
            
        except Exception as e:
            logger.error(f"대화 컨텍스트 조회 중 예외: {str(e)}")
            return {'success': False, 'error': f'대화 컨텍스트 조회 오류: {str(e)}', 'context_blocks': []}
    
    # BaseRepository 인터페이스의 나머지 메서드들 - ChatRepository는 대화 관련만 처리
    def check_user_whitelist(self, email: str, user_id: str) -> Dict[str, Any]:
        """화이트리스트 검증 - AuthRepository에서 처리되어야 함"""
        logger.warning("ChatRepository에서 check_user_whitelist 호출됨 - AuthRepository를 사용하세요")
        return {"success": False, "error": "ChatRepository는 화이트리스트 검증을 지원하지 않습니다"}
    
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 데이터 저장 - AuthRepository에서 처리되어야 함"""
        logger.warning("ChatRepository에서 save_user_data 호출됨 - AuthRepository를 사용하세요")
        return {"success": False, "error": "ChatRepository는 사용자 데이터 저장을 지원하지 않습니다"}
    
    # 호환성을 위한 별칭 메서드
    def get_conversation_with_context(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """호환성을 위한 별칭 메서드"""
        return self.get_user_conversations(user_id, limit)
