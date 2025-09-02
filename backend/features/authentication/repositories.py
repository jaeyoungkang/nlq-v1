"""
Authentication Repository
인증 관련 데이터 접근 계층 - 화이트리스트 검증만 (Firestore 구현)
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from google.cloud import firestore
from core.repositories.firestore_base import FirestoreRepository
from core.models import ContextBlock
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class AuthRepository(FirestoreRepository):
    """
    인증 관련 데이터 접근 계층 (Firestore 구현)
    whitelist 컬렉션 전담 관리
    """
    
    def __init__(self, project_id: Optional[str] = None):
        # whitelist 컬렉션 사용 (화이트리스트 전용)
        super().__init__(collection_name="whitelist", project_id=project_id)
    
    def check_user_whitelist(self, email: str, user_id: str) -> Dict[str, Any]:
        """
        사용자 화이트리스트 검증 (Firestore 구현)
        BaseRepository 인터페이스 구현
        
        whitelist 컬렉션에서 user_id로 조회
        """
        try:
            # whitelist 컬렉션에서 Google user_id로 직접 조회
            whitelist_ref = self.client.collection("whitelist").document(user_id)
            whitelist_doc = whitelist_ref.get()
            
            if not whitelist_doc.exists:
                # 이메일로 검색 시도 (이관을 위한 호환성)
                whitelist_collection = self.client.collection("whitelist")
                query = whitelist_collection.where(filter=firestore.FieldFilter("email", "==", email)).limit(1)
                
                docs = list(query.stream())
                
                if not docs:
                    return {
                        'success': True,
                        'allowed': False,
                        'message': '접근이 허용되지 않은 계정입니다',
                        'reason': 'not_whitelisted'
                    }
                
                # 기존 문서를 user_id 기반으로 이관
                old_doc = docs[0]
                old_data = old_doc.to_dict()
                old_data['user_id'] = user_id
                
                # 새 문서 생성
                whitelist_ref.set(old_data, merge=True)
                logger.info(f"화이트리스트 문서 이관: {old_doc.id} -> {user_id}")
                
                # 기존 문서 삭제 (선택적)
                old_doc.reference.delete()
                
                user_data = old_data
            else:
                user_data = whitelist_doc.to_dict()
            
            # 상태에 따른 접근 확인
            status = user_data.get('status', 'pending')
            if status == 'active':
                # 로그인 시간 업데이트
                try:
                    self._update_last_login(user_id)
                except Exception as e:
                    logger.warning(f"로그인 시간 업데이트 실패: {email}, 오류: {str(e)}")
                
                return {
                    'success': True,
                    'allowed': True,
                    'message': '접근 허용',
                    'user_data': {
                        'user_id': user_id,  # Google user_id 사용
                        'email': user_data.get('email', email),
                        'status': status,
                        'created_at': user_data.get('created_at')
                    }
                }
            elif status == 'pending':
                return {
                    'success': True,
                    'allowed': False,
                    'message': '계정 승인이 대기 중입니다',
                    'reason': 'pending_approval',
                    'status': 'pending'
                }
            else:
                return {
                    'success': True,
                    'allowed': False,
                    'message': '계정이 비활성화되었습니다',
                    'reason': 'account_disabled',
                    'status': status
                }
            
        except Exception as e:
            logger.error(f"화이트리스트 검증 중 예외: {str(e)}")
            return {'success': False, 'error': f'화이트리스트 검증 오류: {str(e)}'}
    
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 데이터 저장 (Firestore 구현)
        BaseRepository 인터페이스 구현
        """
        try:
            user_id = user_data.get('user_id') or user_data.get('email', 'unknown')
            
            # 생성 시간이 없으면 추가
            if 'created_at' not in user_data:
                user_data['created_at'] = datetime.now(timezone.utc)
            
            # 사용자 데이터를 users 컬렉션에 저장
            user_ref = self.client.collection("users").document(user_id)
            user_ref.set(user_data, merge=True)  # merge=True로 기존 데이터 보존
            
            logger.info(f"사용자 데이터 저장 완료: {user_id}")
            return {"success": True, "message": "사용자 데이터가 성공적으로 저장되었습니다"}
            
        except Exception as e:
            logger.error(f"사용자 데이터 저장 중 오류: {str(e)}")
            return {"success": False, "error": f"사용자 데이터 저장 실패: {str(e)}"}
    
    def link_session_to_user(self, session_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """
        세션을 사용자에게 연결 (Firestore 구현)
        임시 세션 ID로 저장된 대화들을 실제 사용자 ID로 이동
        """
        try:
            # 임시 세션 사용자의 conversations를 실제 사용자로 이동
            session_user_ref = self.client.collection("users").document(session_id)
            actual_user_ref = self.client.collection("users").document(user_id)
            
            # 임시 세션의 conversations 서브컬렉션 조회
            session_conversations_ref = session_user_ref.collection("conversations")
            session_docs = list(session_conversations_ref.stream())
            
            updated_count = 0
            
            # 각 대화를 실제 사용자의 conversations로 이동
            batch = self.client.batch()
            for doc in session_docs:
                doc_data = doc.to_dict()
                doc_data['user_id'] = user_id  # user_id 업데이트
                
                # 실제 사용자의 conversations에 추가
                actual_conversations_ref = actual_user_ref.collection("conversations")
                new_doc_ref = actual_conversations_ref.document(doc.id)
                batch.set(new_doc_ref, doc_data)
                
                # 임시 세션에서 삭제
                batch.delete(doc.reference)
                updated_count += 1
            
            # 배치 실행
            if updated_count > 0:
                batch.commit()
            
            logger.info(f"세션 연결 완료: {session_id} -> {user_id}, {updated_count}개 대화 이동")
            return {
                'success': True,
                'updated_rows': updated_count,
                'message': f'{updated_count}개의 대화가 계정에 연결되었습니다'
            }
            
        except Exception as e:
            logger.error(f"세션 연결 중 오류: {str(e)}")
            return {'success': False, 'error': f'세션 연결 실패: {str(e)}', 'updated_rows': 0}
    
    def _update_last_login(self, user_id: str) -> None:
        """화이트리스트 사용자 마지막 로그인 시간 업데이트"""
        try:
            whitelist_ref = self.client.collection("whitelist").document(user_id)
            whitelist_ref.update({
                'last_login': datetime.now(timezone.utc)
            })
            
            logger.debug(f"로그인 시간 업데이트 완료: {user_id}")
            
        except Exception as e:
            logger.warning(f"로그인 시간 업데이트 실패: {user_id}, 오류: {str(e)}")
            # 로그인 시간 업데이트 실패는 로그인 자체를 막지 않음
            pass
    
    # BaseRepository 인터페이스의 나머지 메서드들 - AuthRepository는 인증 관련만 처리
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock 저장 - ChatRepository에서 처리되어야 함"""
        logger.warning("AuthRepository에서 save_context_block 호출됨 - ChatRepository를 사용하세요")
        return {"success": False, "error": "AuthRepository는 ContextBlock 저장을 지원하지 않습니다"}
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자 대화 조회 - ChatRepository에서 처리되어야 함"""
        logger.warning("AuthRepository에서 get_user_conversations 호출됨 - ChatRepository를 사용하세요")
        return {"success": False, "error": "AuthRepository는 대화 조회를 지원하지 않습니다", "context_blocks": []}