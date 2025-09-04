"""
MetaSync Repository - GCS 및 BigQuery 데이터 접근 계층
기존 MetaSyncCacheLoader의 모든 기능을 Repository 패턴으로 구현
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

from core.repositories.gcs_base import GCSRepository
from features.metasync.models import (
    MetadataCache, SchemaInfo, EventsTableInfo, 
    CacheStatus, CacheUpdateRequest
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class MetaSyncRepository(GCSRepository):
    """
    MetaSync 데이터 접근 계층
    GCS 캐시 데이터 관리 및 BigQuery 스키마 조회
    기존 MetaSyncCacheLoader와 완전히 호환되는 인터페이스 제공
    """
    
    def __init__(self, bucket_name: str = "nlq-metadata-cache", 
                 project_id: Optional[str] = None,
                 bigquery_location: str = "asia-northeast3"):
        """
        MetaSync Repository 초기화
        
        Args:
            bucket_name: GCS 캐시 버킷 이름
            project_id: Google Cloud 프로젝트 ID
            bigquery_location: BigQuery 데이터 위치
        """
        super().__init__(bucket_name, project_id)
        
        self.bigquery_location = bigquery_location
        self.bigquery_client = bigquery.Client(project=self.project_id, 
                                             location=self.bigquery_location)
        
        # 메모리 캐시 관리
        self._cache_data: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
        self.cache_refresh_interval = timedelta(hours=1)
        
        # 캐시 파일 경로
        self.cache_file_path = "metadata_cache.json"
    
    # ====== 기존 MetaSyncCacheLoader 호환 인터페이스 ======
    
    def _get_cache_data(self) -> Dict[str, Any]:
        """
        기존 MetaSyncCacheLoader와 동일한 인터페이스
        메모리 캐싱을 포함한 캐시 데이터 로드
        """
        return self.get_cache_data()
    
    def get_cache_data(self) -> Dict[str, Any]:
        """
        캐시 데이터를 메모리 캐싱과 함께 로드
        기존 MetaSyncCacheLoader의 _get_cache_data() 메서드와 동일한 동작
        """
        now = datetime.now()
        
        # 메모리 캐시 확인
        if (self._cache_data is None or 
            self._last_loaded is None or 
            (now - self._last_loaded) > self.cache_refresh_interval):
            
            try:
                # GCS에서 캐시 로드 (JSON 문자열을 딕셔너리로 파싱)
                cache_data = self.read_json(self.cache_file_path)
                
                if not cache_data:
                    logger.warning("Cache file does not exist or is empty in GCS")
                    cache_data = self._get_empty_cache_structure()
                
                self._cache_data = cache_data
                self._last_loaded = now
                logger.info("Cache loaded from GCS")
                
            except Exception as e:
                logger.error(f"Failed to load cache from GCS: {e}")
                self._cache_data = self._get_empty_cache_structure()
        
        return self._cache_data or self._get_empty_cache_structure()
    
    def get_cache_data_raw(self) -> str:
        """
        캐시 데이터를 원본 JSON 문자열로 반환 (순서 보장)
        """
        try:
            # GCS에서 원본 JSON 문자열 직접 읽기
            cache_text = self.read_text(self.cache_file_path)
            
            if not cache_text or cache_text == "{}":
                logger.warning("Cache file does not exist or is empty in GCS")
                import json
                return json.dumps(self._get_empty_cache_structure(), ensure_ascii=False, indent=2)
            
            logger.info("Raw cache loaded from GCS")
            return cache_text
            
        except Exception as e:
            logger.error(f"Failed to load raw cache from GCS: {e}")
            import json
            return json.dumps(self._get_empty_cache_structure(), ensure_ascii=False, indent=2)
    
    def _ensure_correct_order(self, cache_data: Dict[str, Any]) -> Dict[str, Any]:
        """원본 MetaSync와 동일한 순서로 딕셔너리 재정렬"""
        return {
            "generated_at": cache_data.get("generated_at", ""),
            "generation_method": cache_data.get("generation_method", "unknown"),
            "schema": cache_data.get("schema", {}),
            "examples": cache_data.get("examples", []),
            "events_tables": cache_data.get("events_tables", {}),
            "schema_insights": cache_data.get("schema_insights", {})
        }
    
    def _get_empty_cache_structure(self) -> Dict[str, Any]:
        """빈 캐시 구조 반환"""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_method": "unknown",
            "schema": {}, 
            "examples": [], 
            "events_tables": {}, 
            "schema_insights": {}
        }
    
    def get_schema_info(self) -> Dict[str, Any]:
        """스키마 정보 조회 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
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
        """Few-Shot 예시 조회 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            examples = cache_data.get('examples', [])
            
            logger.info(f"Loaded {len(examples)} few-shot examples")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to get few-shot examples: {e}")
            return []
    
    def get_table_id(self) -> str:
        """테이블 ID 조회 - 기존 인터페이스 호환"""
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
    
    def get_events_tables(self) -> List[str]:
        """Events 테이블 목록 반환 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            events_info = cache_data.get('events_tables', {})
            
            events_tables = events_info.get('example_tables', [])
            if events_tables:
                logger.info(f"Using {len(events_tables)} example tables from abstracted info")
            else:
                logger.warning("No example tables found in cache")
            
            return events_tables
            
        except Exception as e:
            logger.error(f"Failed to get events tables: {e}")
            return []
    
    def get_events_tables_info(self) -> Dict[str, Any]:
        """추상화된 events 테이블 정보 반환 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            events_tables_info = cache_data.get('events_tables', {})
            
            if events_tables_info:
                logger.info("Loaded abstracted events tables info from cache")
                return events_tables_info
            else:
                logger.warning("No events tables info in cache")
                return {
                    "count": 0,
                    "pattern": "events_YYYYMMDD",
                    "description": "No events tables available"
                }
                
        except Exception as e:
            logger.error(f"Failed to get events tables info: {e}")
            return {
                "count": 0,
                "pattern": "events_YYYYMMDD",
                "description": "No events tables available"
            }
    
    def get_schema_insights(self) -> Dict[str, Any]:
        """LLM 생성 스키마 인사이트 반환 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            schema_insights = cache_data.get('schema_insights', {})
            
            if schema_insights:
                logger.info("Loaded schema insights from cache")
            else:
                logger.info("No schema insights available in cache")
                
            return schema_insights
            
        except Exception as e:
            logger.error(f"Failed to get schema insights: {e}")
            return {}
    
    def get_generation_method(self) -> str:
        """캐시 생성 방법 조회 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            method = cache_data.get('generation_method', 'unknown')
            
            logger.info(f"Cache generation method: {method}")
            return method
            
        except Exception as e:
            logger.error(f"Failed to get generation method: {e}")
            return 'unknown'
    
    def is_cache_available(self) -> bool:
        """캐시 사용 가능 여부 확인 - 기존 인터페이스 호환"""
        try:
            blob = self.bucket.blob(self.cache_file_path)
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
        """캐시 메타데이터 조회 - 기존 인터페이스 호환"""
        try:
            cache_data = self.get_cache_data()
            
            return {
                'generated_at': cache_data.get('generated_at'),
                'generation_method': cache_data.get('generation_method', 'unknown'),
                'schema_available': bool(cache_data.get('schema')),
                'examples_count': len(cache_data.get('examples', [])),
                'events_tables_count': len(cache_data.get('events_tables', {})),
                'has_schema_insights': bool(cache_data.get('schema_insights')),
                'table_id': cache_data.get('schema', {}).get('table_id'),
                'columns_count': len(cache_data.get('schema', {}).get('columns', [])),
                'llm_enhanced': cache_data.get('generation_method') == 'llm_enhanced'
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache metadata: {e}")
            return {}
    
    def refresh_cache(self) -> bool:
        """캐시 강제 새로고침 - 기존 인터페이스 호환"""
        try:
            self._cache_data = None
            self._last_loaded = None
            
            # 새로 로드
            cache_data = self.get_cache_data()
            
            logger.info("Cache manually refreshed")
            return bool(cache_data)
            
        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            return False
    
    # ====== 새로운 Repository 메서드들 (캐시 생성/업데이트) ======
    
    def save_cache(self, metadata_cache: MetadataCache, 
                   create_snapshot: bool = True) -> Dict[str, Any]:
        """
        메타데이터 캐시를 GCS에 저장
        
        Args:
            metadata_cache: 저장할 메타데이터 캐시
            create_snapshot: 스냅샷 생성 여부
            
        Returns:
            저장 결과
        """
        try:
            cache_data = metadata_cache.to_dict()
            
            # GCS에 저장
            success = self.write_json(
                self.cache_file_path, 
                cache_data, 
                create_snapshot=create_snapshot
            )
            
            if success:
                # 메모리 캐시 업데이트
                self._cache_data = cache_data
                self._last_loaded = datetime.now()
                
                logger.info("Metadata cache saved successfully")
                return {
                    "success": True,
                    "message": "Cache saved successfully",
                    "generated_at": cache_data.get('generated_at'),
                    "snapshot_created": create_snapshot
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to write cache to GCS"
                }
                
        except Exception as e:
            logger.error(f"Failed to save cache: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_cache_status(self) -> CacheStatus:
        """
        캐시 상태 정보 조회
        
        Returns:
            CacheStatus 객체
        """
        try:
            # 파일 존재 여부 및 메타데이터 확인
            blob_metadata = self.get_blob_metadata(self.cache_file_path)
            
            if not blob_metadata:
                return CacheStatus(
                    exists=False,
                    last_updated=None,
                    size_bytes=None,
                    table_count=0,
                    example_count=0,
                    is_valid=False,
                    error_message="Cache file does not exist"
                )
            
            # 캐시 데이터 조회
            cache_data = self.get_cache_data()
            
            return CacheStatus(
                exists=True,
                last_updated=blob_metadata.get('updated'),
                size_bytes=blob_metadata.get('size'),
                table_count=len(cache_data.get('schema', {})),
                example_count=len(cache_data.get('examples', [])),
                is_valid=self.is_cache_available()
            )
            
        except Exception as e:
            logger.error(f"Failed to get cache status: {str(e)}")
            return CacheStatus(
                exists=False,
                last_updated=None,
                size_bytes=None,
                table_count=0,
                example_count=0,
                is_valid=False,
                error_message=str(e)
            )
    
    def fetch_bigquery_schema(self, table_id: str) -> SchemaInfo:
        """
        BigQuery 테이블 스키마 조회
        
        Args:
            table_id: BigQuery 테이블 ID (project.dataset.table 형식)
            
        Returns:
            SchemaInfo 객체
        """
        try:
            table = self.bigquery_client.get_table(table_id)
            
            columns = []
            for field in table.schema:
                columns.append({
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                })
            
            schema_info = SchemaInfo(
                table_id=table_id,
                column_count=len(columns),
                columns=columns,
                last_modified=datetime.now(timezone.utc).isoformat(),
                description=table.description or ""
            )
            
            logger.info(f"Fetched schema for {table_id} with {len(columns)} columns")
            return schema_info
            
        except Exception as e:
            logger.error(f"Failed to fetch schema for {table_id}: {str(e)}")
            raise
    
    def fetch_events_tables_list(self, target_table: str) -> List[str]:
        """
        dataset에서 events_ 패턴 테이블 목록 수집
        
        Args:
            target_table: 기준 테이블 ID (project.dataset.table 형식)
            
        Returns:
            events 테이블 ID 목록
        """
        try:
            # target_table에서 dataset 정보 추출
            table_parts = target_table.split('.')
            if len(table_parts) < 2:
                logger.warning(f"Invalid table format: {target_table}")
                return []
            
            project_id = table_parts[0]
            dataset_id = table_parts[1]
            
            # dataset의 모든 테이블 조회
            dataset_ref = self.bigquery_client.dataset(dataset_id, project=project_id)
            tables = list(self.bigquery_client.list_tables(dataset_ref))
            
            # events_ 패턴 필터링 및 정렬
            events_tables = []
            for table in tables:
                if table.table_id.startswith('events_'):
                    full_table_id = f"{project_id}.{dataset_id}.{table.table_id}"
                    events_tables.append(full_table_id)
            
            events_tables.sort()
            
            logger.info(f"Found {len(events_tables)} events tables in dataset {dataset_id}")
            return events_tables
            
        except Exception as e:
            logger.error(f"Failed to fetch events tables: {str(e)}")
            return []
    
    def fetch_sample_data(self, table_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        테이블의 샘플 데이터 조회
        
        Args:
            table_id: BigQuery 테이블 ID
            limit: 조회할 행 수
            
        Returns:
            샘플 데이터 목록
        """
        try:
            query = f"""
            SELECT *
            FROM `{table_id}`
            ORDER BY RAND()
            LIMIT {limit}
            """
            
            query_job = self.bigquery_client.query(query)
            results = query_job.result()
            
            sample_data = []
            for row in results:
                sample_data.append(dict(row))
            
            logger.info(f"Fetched {len(sample_data)} sample rows from {table_id}")
            return sample_data
            
        except Exception as e:
            logger.error(f"Failed to fetch sample data from {table_id}: {str(e)}")
            return []
    
    def list_cache_snapshots(self) -> List[str]:
        """
        캐시 스냅샷 목록 조회
        
        Returns:
            스냅샷 파일 경로 목록
        """
        try:
            snapshots = self.list_blobs(prefix="snapshots/")
            snapshots.sort(reverse=True)  # 최신순 정렬
            
            logger.info(f"Found {len(snapshots)} cache snapshots")
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to list cache snapshots: {str(e)}")
            return []


# 전역 인스턴스 (싱글톤 패턴) - 기존 호환성
_metasync_repository = None

def get_metasync_repository(bucket_name: str = "nlq-metadata-cache",
                          project_id: Optional[str] = None,
                          bigquery_location: str = "asia-northeast3") -> MetaSyncRepository:
    """
    MetaSyncRepository 싱글톤 인스턴스 반환
    기존 get_metasync_cache_loader()와 유사한 패턴
    """
    global _metasync_repository
    
    if _metasync_repository is None:
        _metasync_repository = MetaSyncRepository(bucket_name, project_id, bigquery_location)
        logger.info(f"Created MetaSyncRepository for bucket: {bucket_name}")
    
    return _metasync_repository