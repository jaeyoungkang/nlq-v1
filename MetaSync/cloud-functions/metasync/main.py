import functions_framework
import json
import logging
import os
from datetime import datetime, timedelta
from google.cloud import bigquery, storage
from google.cloud import secretmanager

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetaSyncManager:
    def __init__(self, project_id, target_table, cache_bucket):
        self.project_id = project_id
        self.target_table = target_table
        self.cache_bucket = cache_bucket
        self.bigquery_client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        self.bucket = self.storage_client.bucket(cache_bucket)
    
    def get_anthropic_api_key(self):
        """Secret Manager에서 API 키 가져오기"""
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.project_id}/secrets/anthropic-api-key/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"Failed to get API key from Secret Manager: {e}")
            return None
    
    def fetch_schema(self):
        """BigQuery 테이블 스키마 조회"""
        try:
            table = self.bigquery_client.get_table(self.target_table)
            schema_info = {
                "table_id": self.target_table,
                "last_updated": datetime.now().isoformat(),
                "columns": []
            }
            
            for field in table.schema:
                schema_info["columns"].append({
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                })
            
            logger.info(f"Fetched schema for {self.target_table} with {len(schema_info['columns'])} columns")
            return schema_info
            
        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}")
            raise
    
    def generate_examples(self, schema_info):
        """기본 예시 생성 (향후 LLM 연동 예정)"""
        # 현재는 하드코딩된 예시 제공
        # 실제 구현에서는 Anthropic API 호출하여 동적 생성
        examples = [
            {
                "question": "총 이벤트 수는 얼마인가요?",
                "sql": f"SELECT COUNT(*) as total_events FROM `{self.target_table}`"
            },
            {
                "question": "날짜별 이벤트 수를 보여주세요",
                "sql": f"SELECT DATE(event_timestamp) as date, COUNT(*) as event_count FROM `{self.target_table}` GROUP BY 1 ORDER BY 1 DESC LIMIT 10"
            },
            {
                "question": "최근 7일간 이벤트 트렌드는 어떤가요?",
                "sql": f"SELECT DATE(event_timestamp) as date, COUNT(*) as event_count FROM `{self.target_table}` WHERE event_timestamp >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY) GROUP BY 1 ORDER BY 1"
            },
            {
                "question": "이벤트 타입별 분포를 알려주세요",
                "sql": f"SELECT event_name, COUNT(*) as count FROM `{self.target_table}` GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
            },
            {
                "question": "시간대별 이벤트 패턴을 분석해주세요",
                "sql": f"SELECT EXTRACT(HOUR FROM event_timestamp) as hour, COUNT(*) as event_count FROM `{self.target_table}` GROUP BY 1 ORDER BY 1"
            }
        ]
        
        logger.info(f"Generated {len(examples)} examples")
        return examples
    
    def is_cache_expired(self, max_age_hours=24):
        """캐시 만료 확인"""
        try:
            blob = self.bucket.blob("metadata_cache.json")
            if not blob.exists():
                logger.info("Cache file does not exist, needs update")
                return True
            
            blob.reload()
            age = datetime.now(blob.updated.tzinfo) - blob.updated
            expired = age > timedelta(hours=max_age_hours)
            
            if expired:
                logger.info(f"Cache expired (age: {age})")
            else:
                logger.info(f"Cache is fresh (age: {age})")
                
            return expired
            
        except Exception as e:
            logger.error(f"Failed to check cache expiration: {e}")
            return True
    
    def save_cache(self, schema_info, examples):
        """GCS에 캐시 저장"""
        try:
            cache_data = {
                "generated_at": datetime.now().isoformat(),
                "schema": schema_info,
                "examples": examples
            }
            
            blob = self.bucket.blob("metadata_cache.json")
            blob.upload_from_string(
                json.dumps(cache_data, indent=2, ensure_ascii=False),
                content_type='application/json'
            )
            
            logger.info(f"Cache saved successfully (size: {len(json.dumps(cache_data))} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            raise
    
    def update_metadata(self):
        """메타데이터 업데이트 실행"""
        logger.info(f"Starting metadata update for {self.target_table}")
        
        # 1. 스키마 조회
        schema_info = self.fetch_schema()
        
        # 2. 예시 생성
        examples = self.generate_examples(schema_info)
        
        # 3. 캐시 저장
        self.save_cache(schema_info, examples)
        
        logger.info("Metadata update completed successfully")
        
        return {
            "updated": True,
            "examples_count": len(examples),
            "columns_count": len(schema_info['columns']),
            "table_id": schema_info['table_id']
        }
    
    def check_and_update_if_needed(self):
        """필요시에만 업데이트"""
        if self.is_cache_expired():
            logger.info("Cache expired, updating...")
            return self.update_metadata()
        else:
            logger.info("Cache is fresh, no update needed")
            return {"updated": False}

@functions_framework.http
def update_metadata_cache(request):
    """HTTP Cloud Function 진입점"""
    start_time = datetime.now()
    
    try:
        # 환경변수 로드
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        target_table = os.getenv('TARGET_TABLE_ID', 'nlq-ex.test_dataset.events_20210131')
        cache_bucket = os.getenv('GCS_BUCKET', 'nlq-metadata-cache')
        
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        logger.info(f"Starting MetaSync for project: {project_id}")
        logger.info(f"Target table: {target_table}")
        logger.info(f"Cache bucket: {cache_bucket}")
        
        # MetaSync 실행
        metasync = MetaSyncManager(project_id, target_table, cache_bucket)
        result = metasync.check_and_update_if_needed()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        response_data = {
            "status": "success",
            "message": "MetaSync completed successfully",
            "execution_time": execution_time,
            "timestamp": start_time.isoformat(),
            **result
        }
        
        logger.info(f"MetaSync completed in {execution_time:.2f}s - {response_data}")
        
        return response_data, 200
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        
        logger.error(f"MetaSync failed after {execution_time:.2f}s: {error_msg}", exc_info=True)
        
        error_response = {
            "status": "error",
            "message": error_msg,
            "execution_time": execution_time,
            "timestamp": start_time.isoformat()
        }
        
        return error_response, 500