"""
Firestore Base Repository
Provides Firestore-specific implementation of BaseRepository
"""

import os
from typing import Dict, Any, Optional, List
from google.cloud import firestore
from google.cloud.exceptions import NotFound
from datetime import datetime
from core.models import ContextBlock, BlockType
from core.repositories.base import BaseRepository
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class FirestoreClient:
    """Firestore 클라이언트 싱글톤"""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._init_client()
        return cls._instance
    
    @classmethod 
    def _init_client(cls):
        """Firestore 클라이언트 싱글톤 초기화"""
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        
        # 로컬 개발 환경 (에뮬레이터)
        if os.getenv('FIRESTORE_EMULATOR_HOST'):
            cls._client = firestore.Client(project=project_id)
            logger.info(f"Firestore 에뮬레이터 클라이언트 초기화: {project_id}")
            return
            
        # 프로덕션 환경 (서비스 계정)
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            cls._client = firestore.Client(project=project_id)
            logger.info(f"Firestore 서비스 계정 클라이언트 초기화: {project_id}")
        else:
            # Cloud Run/GKE 환경 (기본 서비스 계정)
            cls._client = firestore.Client(project=project_id)
            logger.info(f"Firestore 기본 클라이언트 초기화: {project_id}")
    
    @property
    def client(self):
        return self._client


class FirestoreRepository(BaseRepository):
    """
    Firestore 기반 리포지토리 클래스
    BaseRepository 인터페이스의 Firestore 구현체
    """
    
    def __init__(self, collection_name: str, project_id: Optional[str] = None):
        """
        FirestoreRepository 초기화
        
        Args:
            collection_name: Firestore 컬렉션명
            project_id: Google Cloud 프로젝트 ID (기본값: 환경변수)
        """
        self.collection_name = collection_name
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        
        if not self.project_id:
            raise ValueError("Google Cloud 프로젝트 ID가 설정되지 않았습니다")
        
        try:
            self.firestore_client = FirestoreClient()
            self.client = self.firestore_client.client
            logger.info(f"FirestoreRepository 초기화 완료: {collection_name}")
        except Exception as e:
            logger.error(f"FirestoreRepository 초기화 실패: {str(e)}")
            raise
    
    def save(self, data: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
        """
        데이터를 Firestore에 저장
        
        Args:
            data: 저장할 데이터 딕셔너리
            document_id: 문서 ID (없으면 자동 생성)
            
        Returns:
            저장 결과 딕셔너리
        """
        try:
            # datetime 필드 처리
            processed_data = self._serialize_datetime_fields(data.copy())
            
            # 컬렉션 참조 가져오기
            collection_ref = self.client.collection(self.collection_name)
            
            if document_id:
                # 특정 문서 ID로 저장
                doc_ref = collection_ref.document(document_id)
                doc_ref.set(processed_data)
                logger.info(f"데이터 저장 성공: {self.collection_name}/{document_id}")
                return {"success": True, "document_id": document_id, "message": "데이터가 성공적으로 저장되었습니다"}
            else:
                # 자동 문서 ID 생성
                doc_ref = collection_ref.add(processed_data)[1]
                document_id = doc_ref.id
                logger.info(f"데이터 저장 성공: {self.collection_name}/{document_id}")
                return {"success": True, "document_id": document_id, "message": "데이터가 성공적으로 저장되었습니다"}
            
        except Exception as e:
            logger.error(f"데이터 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def find_by_user_id(self, user_id: str, limit: int = 10, order_by: str = "timestamp", direction: str = "desc") -> Dict[str, Any]:
        """
        사용자 ID로 문서 조회
        
        Args:
            user_id: 사용자 ID
            limit: 조회 제한 개수
            order_by: 정렬 필드
            direction: 정렬 방향 ("asc" 또는 "desc")
            
        Returns:
            조회 결과 딕셔너리
        """
        try:
            collection_ref = self.client.collection(self.collection_name)
            query = collection_ref.where("user_id", "==", user_id)
            
            # 정렬 적용
            if direction == "desc":
                query = query.order_by(order_by, direction=firestore.Query.DESCENDING)
            else:
                query = query.order_by(order_by, direction=firestore.Query.ASCENDING)
            
            # 제한 적용
            query = query.limit(limit)
            
            # 쿼리 실행
            docs = query.stream()
            
            results = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data['document_id'] = doc.id
                results.append(doc_data)
            
            logger.info(f"사용자 데이터 조회 완료: {user_id}, {len(results)}개 문서")
            return {"success": True, "data": results, "count": len(results)}
            
        except Exception as e:
            logger.error(f"데이터 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "data": []}
    
    def find_by_id(self, document_id: str) -> Dict[str, Any]:
        """
        문서 ID로 단일 문서 조회
        
        Args:
            document_id: 문서 ID
            
        Returns:
            조회 결과 딕셔너리
        """
        try:
            doc_ref = self.client.collection(self.collection_name).document(document_id)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                doc_data['document_id'] = doc.id
                logger.info(f"문서 조회 성공: {self.collection_name}/{document_id}")
                return {"success": True, "data": doc_data}
            else:
                logger.info(f"문서 없음: {self.collection_name}/{document_id}")
                return {"success": False, "error": "문서를 찾을 수 없습니다", "data": None}
                
        except Exception as e:
            logger.error(f"문서 조회 중 오류: {str(e)}")
            return {"success": False, "error": str(e), "data": None}
    
    def update(self, document_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        문서 업데이트
        
        Args:
            document_id: 문서 ID
            data: 업데이트할 데이터
            
        Returns:
            업데이트 결과 딕셔너리
        """
        try:
            processed_data = self._serialize_datetime_fields(data.copy())
            
            doc_ref = self.client.collection(self.collection_name).document(document_id)
            doc_ref.update(processed_data)
            
            logger.info(f"문서 업데이트 성공: {self.collection_name}/{document_id}")
            return {"success": True, "document_id": document_id, "message": "문서가 성공적으로 업데이트되었습니다"}
            
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def delete(self, document_id: str) -> Dict[str, Any]:
        """
        문서 삭제
        
        Args:
            document_id: 문서 ID
            
        Returns:
            삭제 결과 딕셔너리
        """
        try:
            doc_ref = self.client.collection(self.collection_name).document(document_id)
            doc_ref.delete()
            
            logger.info(f"문서 삭제 성공: {self.collection_name}/{document_id}")
            return {"success": True, "document_id": document_id, "message": "문서가 성공적으로 삭제되었습니다"}
            
        except Exception as e:
            logger.error(f"문서 삭제 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _serialize_datetime_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """datetime 필드를 Firestore Timestamp로 변환"""
        for key, value in data.items():
            if isinstance(value, datetime):
                # Firestore는 자동으로 datetime을 Timestamp로 변환
                data[key] = value
            elif isinstance(value, str) and key == 'timestamp':
                # ISO 형식 문자열을 datetime으로 변환
                try:
                    data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    # 변환 실패 시 원래 값 유지
                    pass
            elif isinstance(value, dict):
                data[key] = self._serialize_datetime_fields(value)
            elif isinstance(value, list):
                data[key] = [
                    self._serialize_datetime_fields(item) if isinstance(item, dict) 
                    else item
                    for item in value
                ]
        return data
    
    # BaseRepository 인터페이스 구현 - 기본 스텁, 실제 구현은 하위 클래스에서
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock 저장 - 하위 클래스에서 구현 필요"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자 대화 조회 - 하위 클래스에서 구현 필요"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")
    
    def check_user_whitelist(self, email: str, user_id: str) -> Dict[str, Any]:
        """화이트리스트 검증 - 하위 클래스에서 구현 필요"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")
    
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 데이터 저장 - 하위 클래스에서 구현 필요"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")