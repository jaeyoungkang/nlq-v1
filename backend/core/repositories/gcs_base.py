"""
GCS (Google Cloud Storage) Repository 기반 클래스
MetaSync 및 기타 GCS 기반 기능을 위한 추상 클래스
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from google.cloud import storage
from google.cloud.exceptions import NotFound
import os
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class GCSClient:
    """Google Cloud Storage 클라이언트 싱글톤"""
    
    _instance: Optional[storage.Client] = None
    
    @classmethod
    def get_client(cls, project_id: Optional[str] = None) -> storage.Client:
        """GCS 클라이언트 인스턴스 반환"""
        if cls._instance is None:
            project = project_id or os.environ.get('GOOGLE_CLOUD_PROJECT', 'nlq-ex')
            cls._instance = storage.Client(project=project)
        return cls._instance


class GCSRepository(ABC):
    """
    GCS Repository 추상 클래스
    Google Cloud Storage 접근을 위한 기본 기능 제공
    """
    
    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        """
        GCS Repository 초기화
        
        Args:
            bucket_name: GCS 버킷 이름
            project_id: Google Cloud 프로젝트 ID (선택적)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id or os.environ.get('GOOGLE_CLOUD_PROJECT', 'nlq-ex')
        self.client = GCSClient.get_client(self.project_id)
        
        try:
            self.bucket = self.client.bucket(bucket_name)
            if not self.bucket.exists():
                logger.warning(f"Bucket {bucket_name} does not exist. Creating it...")
                self.bucket = self.client.create_bucket(bucket_name, location="asia-northeast3")
                logger.info(f"Bucket {bucket_name} created successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GCS bucket {bucket_name}: {str(e)}")
            raise
    
    def read_json(self, blob_path: str) -> Dict[str, Any]:
        """
        GCS에서 JSON 파일 읽기 (딕셔너리로 파싱)
        
        Args:
            blob_path: 파일 경로 (예: "metadata_cache.json")
            
        Returns:
            JSON 데이터 딕셔너리
        """
        try:
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Blob {blob_path} not found in bucket {self.bucket_name}")
                return {}
            
            content = blob.download_as_text()
            return json.loads(content)
        except NotFound:
            logger.warning(f"File {blob_path} not found in GCS")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from {blob_path}: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Failed to read {blob_path} from GCS: {str(e)}")
            raise

    def read_text(self, blob_path: str) -> str:
        """
        GCS에서 텍스트 파일 읽기 (원본 문자열 그대로)
        
        Args:
            blob_path: 파일 경로 (예: "metadata_cache.json")
            
        Returns:
            파일 내용 문자열
        """
        try:
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Blob {blob_path} not found in bucket {self.bucket_name}")
                return "{}"
            
            content = blob.download_as_text()
            return content
        except NotFound:
            logger.warning(f"File {blob_path} not found in GCS")
            return "{}"
        except Exception as e:
            logger.error(f"Failed to read {blob_path} from GCS: {str(e)}")
            return "{}"
    
    def write_json(self, blob_path: str, data: Dict[str, Any], 
                   create_snapshot: bool = False) -> bool:
        """
        GCS에 JSON 파일 쓰기
        
        Args:
            blob_path: 파일 경로 (예: "metadata_cache.json")
            data: 저장할 JSON 데이터
            create_snapshot: 스냅샷 생성 여부
            
        Returns:
            성공 여부
        """
        try:
            # 스냅샷 생성 (선택적)
            if create_snapshot:
                self._create_snapshot(blob_path, data)
            
            # 메인 파일 저장
            blob = self.bucket.blob(blob_path)
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            
            blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            logger.info(f"Successfully wrote {blob_path} to GCS")
            return True
        except Exception as e:
            logger.error(f"Failed to write {blob_path} to GCS: {str(e)}")
            return False
    
    def _create_snapshot(self, blob_path: str, data: Dict[str, Any]) -> Optional[str]:
        """
        스냅샷 생성 (백업용)
        
        Args:
            blob_path: 원본 파일 경로
            data: 저장할 데이터
            
        Returns:
            스냅샷 경로 또는 None
        """
        try:
            # 타임스탬프 기반 스냅샷 경로 생성
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
            base_name = blob_path.replace('.json', '')
            snapshot_path = f"snapshots/{base_name}_{timestamp}.json"
            
            # 스냅샷 저장
            snapshot_blob = self.bucket.blob(snapshot_path)
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            
            snapshot_blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            logger.info(f"Created snapshot: {snapshot_path}")
            return snapshot_path
        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")
            return None
    
    def list_blobs(self, prefix: Optional[str] = None) -> List[str]:
        """
        버킷 내 파일 목록 조회
        
        Args:
            prefix: 경로 접두어 (예: "snapshots/")
            
        Returns:
            파일 경로 목록
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list blobs: {str(e)}")
            return []
    
    def delete_blob(self, blob_path: str) -> bool:
        """
        GCS에서 파일 삭제
        
        Args:
            blob_path: 삭제할 파일 경로
            
        Returns:
            성공 여부
        """
        try:
            blob = self.bucket.blob(blob_path)
            if blob.exists():
                blob.delete()
                logger.info(f"Deleted {blob_path} from GCS")
                return True
            else:
                logger.warning(f"Blob {blob_path} does not exist")
                return False
        except Exception as e:
            logger.error(f"Failed to delete {blob_path}: {str(e)}")
            return False
    
    def get_blob_metadata(self, blob_path: str) -> Dict[str, Any]:
        """
        파일 메타데이터 조회
        
        Args:
            blob_path: 파일 경로
            
        Returns:
            메타데이터 딕셔너리
        """
        try:
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                return {}
            
            blob.reload()
            
            return {
                "size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "etag": blob.etag,
                "generation": blob.generation,
                "metageneration": blob.metageneration
            }
        except Exception as e:
            logger.error(f"Failed to get metadata for {blob_path}: {str(e)}")
            return {}