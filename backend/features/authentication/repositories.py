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
    
    def check_user_whitelist(self, email: str, user_id: str = None) -> Dict[str, Any]:
        """
        사용자 화이트리스트 검증 (Firestore 구현) - 이메일 기반 단순화
        BaseRepository 인터페이스 구현
        
        whitelist 컬렉션에서 이메일로 직접 조회
        문서 존재하면 허용, 존재하지 않으면 차단
        """
        try:
            # whitelist 컬렉션에서 이메일을 문서 ID로 직접 조회
            whitelist_ref = self.client.collection("whitelist").document(email)
            whitelist_doc = whitelist_ref.get()
            
            if not whitelist_doc.exists:
                return {
                    'success': True,
                    'allowed': False,
                    'message': '접근이 허용되지 않은 계정입니다',
                    'reason': 'not_whitelisted'
                }
            
            # 화이트리스트에 존재하면 무조건 허용
            user_data = whitelist_doc.to_dict()
            return {
                'success': True,
                'allowed': True,
                'message': '접근 허용',
                'user_data': {
                    'email': email,
                    'created_at': user_data.get('created_at')
                }
            }
            
        except Exception as e:
            logger.error(f"화이트리스트 검증 중 예외: {str(e)}")
            return {'success': False, 'error': f'화이트리스트 검증 오류: {str(e)}'}
    
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        화이트리스트에 사용자 이메일 추가 (단순화된 구조)
        BaseRepository 인터페이스 구현
        """
        try:
            email = user_data.get('email')
            if not email:
                return {"success": False, "error": "이메일이 필요합니다"}
            
            # 단순화된 화이트리스트 데이터 구조
            whitelist_data = {
                'email': email,
                'created_at': datetime.now(timezone.utc)
            }
            
            # 화이트리스트에 이메일을 문서 ID로 저장
            whitelist_ref = self.client.collection("whitelist").document(email)
            whitelist_ref.set(whitelist_data, merge=True)
            
            logger.info(f"화이트리스트에 추가 완료: {email}")
            return {"success": True, "message": "사용자가 화이트리스트에 추가되었습니다"}
            
        except Exception as e:
            logger.error(f"화이트리스트 추가 중 오류: {str(e)}")
            return {"success": False, "error": f"화이트리스트 추가 실패: {str(e)}"}
    
    def ensure_user_document(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """users 컬렉션에 사용자 문서 생성/업데이트 (이메일 기반)"""
        try:
            email = user_info['email']
            
            # users 컬렉션에 이메일을 문서 ID로 사용하여 사용자 기본 정보 저장
            user_ref = self.client.collection("users").document(email)
            
            user_document = {
                'email': email,
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'google_user_id': user_info.get('google_user_id', ''),
                'last_login': datetime.now(timezone.utc),
                'created_at': datetime.now(timezone.utc)  # merge=True로 기존 값 유지
            }
            
            # merge=True로 기존 created_at은 유지, 나머지는 업데이트
            user_ref.set(user_document, merge=True)
            
            logger.info(f"users 문서 생성/업데이트 완료: {email}")
            return {
                "success": True, 
                "message": f"사용자 문서가 생성/업데이트되었습니다: {email}",
                "user_id": email
            }
            
        except Exception as e:
            logger.error(f"users 문서 생성 중 오류: {str(e)}")
            return {"success": False, "error": f"사용자 문서 생성 실패: {str(e)}"}
    
    def link_session_to_user(self, session_id: str, user_email: str) -> Dict[str, Any]:
        """
        세션을 사용자에게 연결 (Firestore 구현)
        임시 세션 ID로 저장된 대화들을 실제 사용자 ID로 이동
        """
        try:
            # 임시 세션 사용자의 conversations를 실제 사용자로 이동 (이메일 기반)
            session_user_ref = self.client.collection("users").document(session_id)
            actual_user_ref = self.client.collection("users").document(user_email)  # 이메일 사용
            
            # 임시 세션의 conversations 서브컬렉션 조회
            session_conversations_ref = session_user_ref.collection("conversations")
            session_docs = list(session_conversations_ref.stream())
            
            updated_count = 0
            
            # 각 대화를 실제 사용자의 conversations로 이동
            batch = self.client.batch()
            for doc in session_docs:
                doc_data = doc.to_dict()
                doc_data['user_id'] = user_email  # 이메일로 user_id 업데이트
                
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
            
            logger.info(f"세션 연결 완료: {session_id} -> {user_email}, {updated_count}개 대화 이동")
            return {
                'success': True,
                'updated_rows': updated_count,
                'message': f'{updated_count}개의 대화가 계정에 연결되었습니다'
            }
            
        except Exception as e:
            logger.error(f"세션 연결 중 오류: {str(e)}")
            return {'success': False, 'error': f'세션 연결 실패: {str(e)}', 'updated_rows': 0}
    
    
    # BaseRepository 인터페이스의 나머지 메서드들 - AuthRepository는 인증 관련만 처리
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock 저장 - ChatRepository에서 처리되어야 함"""
        logger.warning("AuthRepository에서 save_context_block 호출됨 - ChatRepository를 사용하세요")
        return {"success": False, "error": "AuthRepository는 ContextBlock 저장을 지원하지 않습니다"}
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자 대화 조회 - ChatRepository에서 처리되어야 함"""
        logger.warning("AuthRepository에서 get_user_conversations 호출됨 - ChatRepository를 사용하세요")
        return {"success": False, "error": "AuthRepository는 대화 조회를 지원하지 않습니다", "context_blocks": []}