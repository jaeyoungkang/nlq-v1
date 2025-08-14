import json
import logging
from google.cloud import storage
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MetaSyncCacheLoader:
    """MetaSync에서 생성한 캐시 데이터를 로드하는 클래스"""
    
    def __init__(self, gcs_bucket_name: str = "nlq-metadata-cache"):
        """
        Args:
            gcs_bucket_name: GCS 버킷 이름
        """
        self.gcs_bucket_name = gcs_bucket_name
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(gcs_bucket_name)
        self._cache_data = None
        self._last_loaded = None
        self.cache_refresh_interval = timedelta(hours=1)  # 1시간마다 새로고침
        
    def get_schema_info(self) -> Dict[str, Any]:
        """스키마 정보 조회
        
        Returns:
            Dict containing table schema information
        """
        try:
            cache_data = self._get_cache_data()
            schema = cache_data.get('schema', {})
            
            if schema:
                logger.info(f"Loaded schema for table: {schema.get('table_id', 'unknown')}")
            else:
                logger.warning("No schema data available in cache")
                
            return schema
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return {}
    
    def get_few_shot_examples(self) -> List[Dict[str, str]]:
        """Few-Shot 예시 조회
        
        Returns:
            List of example question-SQL pairs
        """
        try:
            cache_data = self._get_cache_data()
            examples = cache_data.get('examples', [])
            
            logger.info(f"Loaded {len(examples)} few-shot examples")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to get few-shot examples: {e}")
            return []
    
    def get_schema_columns(self) -> List[Dict[str, str]]:
        """테이블 컬럼 정보만 추출
        
        Returns:
            List of column information (name, type, description)
        """
        try:
            schema = self.get_schema_info()
            columns = schema.get('columns', [])
            
            # 컬럼 정보 간소화
            simplified_columns = []
            for col in columns:
                simplified_columns.append({
                    'name': col.get('name', ''),
                    'type': col.get('type', ''),
                    'description': col.get('description', '')
                })
            
            logger.info(f"Extracted {len(simplified_columns)} column definitions")
            return simplified_columns
            
        except Exception as e:
            logger.error(f"Failed to get schema columns: {e}")
            return []
    
    def get_table_id(self) -> str:
        """테이블 ID 조회
        
        Returns:
            BigQuery table ID
        """
        try:
            schema = self.get_schema_info()
            table_id = schema.get('table_id', '')
            
            if table_id:
                logger.info(f"Using table ID: {table_id}")
            else:
                logger.warning("No table ID found in cache")
                
            return table_id
            
        except Exception as e:
            logger.error(f"Failed to get table ID: {e}")
            return ""
    
    def is_cache_available(self) -> bool:
        """캐시 데이터 사용 가능 여부 확인
        
        Returns:
            True if cache is available and not expired
        """
        try:
            blob = self.bucket.blob("metadata_cache.json")
            if not blob.exists():
                logger.info("Cache file does not exist")
                return False
            
            # 캐시 만료 확인 (24시간)
            blob.reload()
            age = datetime.now(blob.updated.tzinfo) - blob.updated
            if age > timedelta(hours=24):
                logger.warning(f"Cache is expired (age: {age})")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to check cache availability: {e}")
            return False
    
    def get_cache_metadata(self) -> Dict[str, Any]:
        """캐시 메타데이터 조회
        
        Returns:
            Cache metadata including generation time, stats
        """
        try:
            cache_data = self._get_cache_data()
            
            return {
                'generated_at': cache_data.get('generated_at'),
                'schema_available': bool(cache_data.get('schema')),
                'examples_count': len(cache_data.get('examples', [])),
                'table_id': cache_data.get('schema', {}).get('table_id'),
                'columns_count': len(cache_data.get('schema', {}).get('columns', []))
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache metadata: {e}")
            return {}
    
    def refresh_cache(self) -> bool:
        """강제로 캐시 새로고침
        
        Returns:
            True if refresh successful
        """
        try:
            self._cache_data = None
            self._last_loaded = None
            
            # 새로 로드
            cache_data = self._get_cache_data()
            
            logger.info("Cache manually refreshed")
            return bool(cache_data)
            
        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            return False
    
    def _get_cache_data(self) -> Dict[str, Any]:
        """GCS에서 캐시 데이터 로드 (메모리 캐싱 포함)
        
        Returns:
            Cache data dictionary
        """
        now = datetime.now()
        
        # 메모리 캐시 확인 (1시간 간격으로만 GCS에서 새로 로드)
        if (self._cache_data is None or 
            self._last_loaded is None or 
            (now - self._last_loaded) > self.cache_refresh_interval):
            
            try:
                blob = self.bucket.blob("metadata_cache.json")
                
                if not blob.exists():
                    logger.warning("Cache file does not exist in GCS")
                    self._cache_data = {"schema": {}, "examples": []}
                else:
                    content = blob.download_as_text()
                    self._cache_data = json.loads(content)
                    logger.info("Cache loaded from GCS")
                
                self._last_loaded = now
                
            except Exception as e:
                logger.error(f"Failed to load cache from GCS: {e}")
                # 실패 시 빈 캐시 반환
                self._cache_data = {"schema": {}, "examples": []}
        
        return self._cache_data or {"schema": {}, "examples": []}

# 전역 인스턴스 (싱글톤 패턴)
_metasync_cache_loader = None

def get_metasync_cache_loader(gcs_bucket_name: str = "nlq-metadata-cache") -> MetaSyncCacheLoader:
    """MetaSyncCacheLoader 싱글톤 인스턴스 반환
    
    Args:
        gcs_bucket_name: GCS 버킷 이름
        
    Returns:
        MetaSyncCacheLoader instance
    """
    global _metasync_cache_loader
    
    if _metasync_cache_loader is None:
        _metasync_cache_loader = MetaSyncCacheLoader(gcs_bucket_name)
        logger.info(f"Created MetaSyncCacheLoader for bucket: {gcs_bucket_name}")
    
    return _metasync_cache_loader