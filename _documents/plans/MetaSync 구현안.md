# System A 구현안: 메타데이터 관리 시스템

## 개요

System A는 BigQuery 스키마를 주기적으로 조회하고, LLM을 활용해 SQL 생성에 필요한 핵심 정보를 가공하여 캐시 파일에 저장하는 시스템입니다.

## 아키텍처 설계

### 1. 실행 모델
- **실행 주기**: 1일 1회 또는 테이블 스키마 변경 시 트리거
- **실행 방식**: 배치 작업 또는 스케줄링 시스템
- **출력**: `metadata_cache.json` 파일 생성/업데이트

### 2. 주요 컴포넌트

#### 2.1 Schema Fetcher
```python
class SchemaFetcher:
    def __init__(self, bigquery_client):
        self.client = bigquery_client
    
    def fetch_table_schema(self, table_id: str) -> Dict[str, Any]:
        """BigQuery 테이블의 최신 스키마 정보를 조회"""
        table = self.client.get_table(table_id)
        schema_info = {
            "table_id": table_id,
            "last_updated": datetime.now().isoformat(),
            "columns": []
        }
        
        for field in table.schema:
            column_info = {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description
            }
            schema_info["columns"].append(column_info)
        
        return schema_info
```

#### 2.2 Example Generator
```python
class ExampleGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def generate_few_shot_examples(self, schema_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """스키마 정보를 바탕으로 Few-Shot 예시 생성"""
        prompt = f"""
다음 BigQuery 테이블 스키마를 분석하여 다양하고 유용한 자연어 질문과 
그에 맞는 SQL 쿼리 예시 5개를 생성해주세요.

테이블: {schema_info['table_id']}
컬럼 정보:
{self._format_schema_for_prompt(schema_info)}

각 예시는 다음 형식으로 작성해주세요:
- 질문: [자연어 질문]
- 쿼리: [BigQuery SQL]
        """
        
        response = self.llm_client.generate(prompt)
        return self._parse_examples(response)
    
    def _format_schema_for_prompt(self, schema_info: Dict[str, Any]) -> str:
        """스키마 정보를 프롬프트에 맞는 형식으로 변환"""
        formatted_columns = []
        for col in schema_info['columns']:
            formatted_columns.append(f"- {col['name']} ({col['type']}): {col['description']}")
        return "\n".join(formatted_columns)
    
    def _parse_examples(self, llm_response: str) -> List[Dict[str, str]]:
        """LLM 응답을 파싱하여 구조화된 예시로 변환"""
        # 정규식 또는 문자열 파싱 로직으로 질문-쿼리 쌍 추출
        examples = []
        # 파싱 로직 구현...
        return examples
```

#### 2.3 GCS Cache Manager
```python
from google.cloud import storage
import json
from datetime import datetime, timedelta

class GCSCacheManager:
    def __init__(self, bucket_name: str = "nlq-metadata-cache", 
                 cache_file_name: str = "metadata_cache.json"):
        self.bucket_name = bucket_name
        self.cache_file_name = cache_file_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
    
    def save_cache(self, schema_info: Dict[str, Any], examples: List[Dict[str, str]]):
        """스키마 정보와 예시를 GCS에 저장"""
        cache_data = {
            "schema": schema_info,
            "examples": examples,
            "generated_at": datetime.now().isoformat()
        }
        
        blob = self.bucket.blob(self.cache_file_name)
        blob.upload_from_string(
            json.dumps(cache_data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        
        # 메타데이터 설정으로 캐시 정보 추가
        blob.metadata = {
            'generated_at': cache_data['generated_at'],
            'schema_table': schema_info['table_id'],
            'examples_count': str(len(examples))
        }
        blob.patch()
    
    def load_cache(self) -> Dict[str, Any]:
        """GCS에서 캐시 데이터 로드"""
        try:
            blob = self.bucket.blob(self.cache_file_name)
            if not blob.exists():
                return None
            
            content = blob.download_as_text()
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Failed to load cache from GCS: {e}")
            return None
    
    def is_cache_expired(self, max_age_hours: int = 24) -> bool:
        """캐시가 만료되었는지 확인"""
        try:
            blob = self.bucket.blob(self.cache_file_name)
            if not blob.exists():
                return True
            
            # blob 메타데이터에서 생성 시간 확인
            blob.reload()
            if 'generated_at' in blob.metadata:
                generated_at = datetime.fromisoformat(blob.metadata['generated_at'])
            else:
                # 메타데이터가 없으면 파일 수정 시간 사용
                generated_at = blob.updated
            
            age = datetime.now(generated_at.tzinfo) - generated_at
            return age > timedelta(hours=max_age_hours)
            
        except Exception as e:
            logger.warning(f"Failed to check cache expiration: {e}")
            return True
    
    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 파일 정보 조회"""
        try:
            blob = self.bucket.blob(self.cache_file_name)
            if not blob.exists():
                return {"exists": False}
            
            blob.reload()
            return {
                "exists": True,
                "size": blob.size,
                "updated": blob.updated.isoformat(),
                "metadata": blob.metadata or {}
            }
        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {"exists": False, "error": str(e)}
```

### 3. 메인 실행 클래스

```python
class SystemAManager:
    def __init__(self, bigquery_client, llm_client, cache_manager):
        self.schema_fetcher = SchemaFetcher(bigquery_client)
        self.example_generator = ExampleGenerator(llm_client)
        self.cache_manager = cache_manager
    
    def run_metadata_update(self, table_id: str = "nlq-ex.test_dataset.events_20210131"):
        """메타데이터 업데이트 프로세스 실행"""
        logger.info(f"Starting metadata update for table: {table_id}")
        
        try:
            # 1. 스키마 조회
            schema_info = self.schema_fetcher.fetch_table_schema(table_id)
            logger.info(f"Fetched schema with {len(schema_info['columns'])} columns")
            
            # 2. Few-Shot 예시 생성
            examples = self.example_generator.generate_few_shot_examples(schema_info)
            logger.info(f"Generated {len(examples)} examples")
            
            # 3. 캐시 저장
            self.cache_manager.save_cache(schema_info, examples)
            logger.info("Metadata cache updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
            raise
    
    def check_and_update_if_needed(self):
        """필요시에만 메타데이터 업데이트"""
        if self.cache_manager.is_cache_expired():
            logger.info("Cache expired, updating metadata")
            self.run_metadata_update()
        else:
            logger.info("Cache is fresh, no update needed")
```

## GCP 환경 배포 및 실행 전략 (필수 구성)

### 선택된 옵션: Cloud Scheduler + Cloud Functions

#### 1. 간소화된 Cloud Function 구현

**최소 프로젝트 구조**:
```
cloud-functions/system-a/
├── main.py              # Cloud Function 진입점 (전체 로직 포함)
├── requirements.txt     # 필수 패키지만
└── .env.yaml           # 환경 변수
```

**Cloud Function 메인 코드** (`main.py` - 모든 기능 통합):
```python
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

class SystemAManager:
    def __init__(self, project_id, target_table, cache_bucket):
        self.project_id = project_id
        self.target_table = target_table
        self.cache_bucket = cache_bucket
        self.bigquery_client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        self.bucket = self.storage_client.bucket(cache_bucket)
    
    def get_anthropic_api_key(self):
        """Secret Manager에서 API 키 가져오기"""
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.project_id}/secrets/anthropic-api-key/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    def fetch_schema(self):
        """BigQuery 테이블 스키마 조회"""
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
        
        return schema_info
    
    def generate_examples(self, schema_info):
        """간단한 예시 생성 (LLM 대신 하드코딩된 예시)"""
        # 실제 구현에서는 Anthropic API 호출
        # 현재는 기본 예시만 제공
        examples = [
            {
                "question": "총 이벤트 수는 얼마인가요?",
                "sql": f"SELECT COUNT(*) as total_events FROM `{self.target_table}`"
            },
            {
                "question": "날짜별 이벤트 수를 보여주세요",
                "sql": f"SELECT DATE(event_timestamp) as date, COUNT(*) as event_count FROM `{self.target_table}` GROUP BY 1 ORDER BY 1 DESC LIMIT 10"
            }
        ]
        return examples
    
    def is_cache_expired(self, max_age_hours=24):
        """캐시 만료 확인"""
        try:
            blob = self.bucket.blob("metadata_cache.json")
            if not blob.exists():
                return True
            
            blob.reload()
            age = datetime.now(blob.updated.tzinfo) - blob.updated
            return age > timedelta(hours=max_age_hours)
        except:
            return True
    
    def save_cache(self, schema_info, examples):
        """GCS에 캐시 저장"""
        cache_data = {
            "schema": schema_info,
            "examples": examples,
            "generated_at": datetime.now().isoformat()
        }
        
        blob = self.bucket.blob("metadata_cache.json")
        blob.upload_from_string(
            json.dumps(cache_data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
    
    def update_metadata(self):
        """메타데이터 업데이트 실행"""
        logger.info(f"Updating metadata for {self.target_table}")
        
        # 1. 스키마 조회
        schema_info = self.fetch_schema()
        logger.info(f"Fetched schema with {len(schema_info['columns'])} columns")
        
        # 2. 예시 생성
        examples = self.generate_examples(schema_info)
        logger.info(f"Generated {len(examples)} examples")
        
        # 3. 캐시 저장
        self.save_cache(schema_info, examples)
        logger.info("Cache saved successfully")
        
        return {
            "updated": True,
            "examples_count": len(examples),
            "columns_count": len(schema_info['columns'])
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
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        target_table = os.getenv('TARGET_TABLE_ID', 'nlq-ex.test_dataset.events_20210131')
        cache_bucket = os.getenv('GCS_BUCKET', 'nlq-metadata-cache')
        
        logger.info(f"Starting System A for project: {project_id}")
        
        system_a = SystemAManager(project_id, target_table, cache_bucket)
        result = system_a.check_and_update_if_needed()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"System A completed in {execution_time:.2f}s")
        
        return {
            "status": "success",
            "message": "Metadata update completed",
            "execution_time": execution_time,
            **result
        }, 200
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"System A failed: {e}", exc_info=True)
        
        return {
            "status": "error",
            "message": str(e),
            "execution_time": execution_time
        }, 500
```

**필수 패키지** (`requirements.txt`):
```txt
google-cloud-bigquery==3.11.4
google-cloud-storage==2.10.0
google-cloud-secret-manager==2.16.4
functions-framework==3.4.0
```

**환경 변수** (`.env.yaml`):
```yaml
GOOGLE_CLOUD_PROJECT: "nlq-ex"
TARGET_TABLE_ID: "nlq-ex.test_dataset.events_20210131"
GCS_BUCKET: "nlq-metadata-cache"
```

#### 2. 간단한 배포 설정

**1단계: GCS 버킷 생성**
```bash
gsutil mb -l asia-northeast3 gs://nlq-metadata-cache
```

**2단계: Secret Manager에 API 키 저장**
```bash
echo "your-anthropic-api-key" | gcloud secrets create anthropic-api-key --data-file=-
```

**3단계: Cloud Function 배포**
```bash
cd cloud-functions/system-a

gcloud functions deploy update-metadata-cache \
  --gen2 \
  --region=asia-northeast3 \
  --runtime=python39 \
  --source=. \
  --entry-point=update_metadata_cache \
  --trigger=http \
  --memory=512MiB \
  --timeout=300s \
  --env-vars-file=.env.yaml
```

**4단계: Cloud Scheduler 설정**
```bash
gcloud scheduler jobs create http system-a-scheduler \
  --location=asia-northeast3 \
  --schedule="0 17 * * *" \
  --time-zone="UTC" \
  --uri="https://asia-northeast3-nlq-ex.cloudfunctions.net/update-metadata-cache" \
  --http-method=POST
```

### 결과물 저장 (필수만)

#### GCS 버킷 구조 (단순화)
```
nlq-metadata-cache/
└── metadata_cache.json    # 현재 활성 캐시만
```

#### 캐시 데이터 구조 (필수 필드만)
```json
{
  "generated_at": "2024-01-15T17:00:00Z",
  "schema": {
    "table_id": "nlq-ex.test_dataset.events_20210131",
    "columns": [
      {
        "name": "event_timestamp",
        "type": "TIMESTAMP",
        "mode": "NULLABLE",
        "description": "이벤트 발생 시간"
      }
    ]
  },
  "examples": [
    {
      "question": "총 이벤트 수는 얼마인가요?",
      "sql": "SELECT COUNT(*) as total_events FROM `nlq-ex.test_dataset.events_20210131`"
    },
    {
      "question": "날짜별 이벤트 수를 보여주세요",
      "sql": "SELECT DATE(event_timestamp) as date, COUNT(*) as event_count FROM `nlq-ex.test_dataset.events_20210131` GROUP BY 1 ORDER BY 1 DESC LIMIT 10"
    }
  ]
}
```

### System B 통합 (간단한 캐시 로더)

```python
# backend/utils/cache_loader.py
import json
from google.cloud import storage
from datetime import datetime, timedelta

class CacheLoader:
    def __init__(self, gcs_bucket_name: str = "nlq-metadata-cache"):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(gcs_bucket_name)
        self._cache_data = None
        self._last_loaded = None
    
    def get_schema_info(self):
        """스키마 정보 조회"""
        cache_data = self._get_cache_data()
        return cache_data.get('schema', {})
    
    def get_few_shot_examples(self):
        """Few-Shot 예시 조회"""
        cache_data = self._get_cache_data()
        return cache_data.get('examples', [])
    
    def _get_cache_data(self):
        """GCS에서 캐시 데이터 로드 (1시간 메모리 캐시)"""
        now = datetime.now()
        
        # 1시간마다만 GCS에서 새로 로드
        if (self._cache_data is None or 
            self._last_loaded is None or 
            (now - self._last_loaded) > timedelta(hours=1)):
            
            try:
                blob = self.bucket.blob("metadata_cache.json")
                if blob.exists():
                    content = blob.download_as_text()
                    self._cache_data = json.loads(content)
                    self._last_loaded = now
                else:
                    self._cache_data = {"schema": {}, "examples": []}
            except:
                self._cache_data = {"schema": {}, "examples": []}
        
        return self._cache_data
```

### 로컬 테스트

```bash
# 로컬에서 Cloud Function 테스트
functions-framework --target=update_metadata_cache --port=8080

# 테스트 호출
curl -X POST http://localhost:8080
```

### 수동 테스트

```bash
# Cloud Function 직접 테스트
gcloud functions call update-metadata-cache \
  --region=asia-northeast3 \
  --data='{}'

# Scheduler 수동 실행
gcloud scheduler jobs run system-a-scheduler --location=asia-northeast3

# GCS에서 결과 확인
gsutil cat gs://nlq-metadata-cache/metadata_cache.json
```

## GCP 모니터링 및 로깅

### 1. Cloud Logging 설정
```python
import google.cloud.logging
import logging

# Cloud Logging 클라이언트 설정
client = google.cloud.logging.Client()
client.setup_logging()

# 구조화된 로깅
logger = logging.getLogger('system_a')
logger.setLevel(logging.INFO)

# 로그 엔트리에 메타데이터 추가
def log_with_metadata(level, message, **kwargs):
    extra_data = {
        'component': 'system_a',
        'project_id': os.getenv('GOOGLE_CLOUD_PROJECT'),
        **kwargs
    }
    logger.log(level, message, extra=extra_data)
```

### 2. Cloud Monitoring 메트릭
```python
from google.cloud import monitoring_v3
import time

class MetricsClient:
    def __init__(self):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}"
    
    def send_success_metric(self, execution_time: float):
        """성공 메트릭 전송"""
        self._send_metric(
            "custom.googleapis.com/system_a/success_count", 
            1, 
            execution_time=execution_time
        )
    
    def send_failure_metric(self, error_type: str):
        """실패 메트릭 전송"""
        self._send_metric(
            "custom.googleapis.com/system_a/failure_count", 
            1,
            error_type=error_type
        )
    
    def _send_metric(self, metric_type: str, value: int, **labels):
        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_type
        series.resource.type = "global"
        
        # 라벨 추가
        for key, val in labels.items():
            series.metric.labels[key] = str(val)
        
        point = monitoring_v3.Point()
        point.value.int64_value = value
        point.interval.end_time.seconds = int(time.time())
        series.points = [point]
        
        self.client.create_time_series(
            name=self.project_name,
            time_series=[series]
        )
```

### 3. 알림 설정

#### Pub/Sub 기반 알림
```python
from google.cloud import pubsub_v1
import json

class NotificationService:
    def __init__(self, topic_name: str = "system-a-notifications"):
        self.publisher = pubsub_v1.PublisherClient()
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.topic_path = self.publisher.topic_path(self.project_id, topic_name)
    
    def send_failure_alert(self, error_message: str, stack_trace: str = None):
        """실패 알림 발송"""
        message_data = {
            "type": "system_a_failure",
            "timestamp": datetime.now().isoformat(),
            "error_message": error_message,
            "stack_trace": stack_trace,
            "project_id": self.project_id
        }
        
        # JSON 직렬화
        message_json = json.dumps(message_data)
        message_bytes = message_json.encode('utf-8')
        
        # Pub/Sub로 메시지 발송
        future = self.publisher.publish(self.topic_path, message_bytes)
        future.result()  # 발송 완료 대기
    
    def send_success_notification(self, metadata: Dict[str, Any]):
        """성공 알림 발송"""
        message_data = {
            "type": "system_a_success",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "project_id": self.project_id
        }
        
        message_json = json.dumps(message_data)
        message_bytes = message_json.encode('utf-8')
        
        future = self.publisher.publish(self.topic_path, message_bytes)
        future.result()
```

### 4. Cloud Monitoring 대시보드
```yaml
# monitoring-dashboard.yaml
displayName: "System A Monitoring"
mosaicLayout:
  tiles:
  - width: 6
    height: 4
    widget:
      title: "System A Execution Success Rate"
      scorecard:
        timeSeriesQuery:
          timeSeriesFilter:
            filter: 'metric.type="custom.googleapis.com/system_a/success_count"'
            aggregation:
              alignmentPeriod: "3600s"
              perSeriesAligner: "ALIGN_SUM"
  - width: 6
    height: 4
    widget:
      title: "System A Failures"
      scorecard:
        timeSeriesQuery:
          timeSeriesFilter:
            filter: 'metric.type="custom.googleapis.com/system_a/failure_count"'
            aggregation:
              alignmentPeriod: "3600s"
              perSeriesAligner: "ALIGN_SUM"
```

## 확장 계획

### 1. 다중 테이블 지원
- 여러 테이블의 스키마를 관리할 수 있도록 확장
- 테이블별 캐시 파일 분리 또는 통합 캐시 구조 설계

### 2. 스키마 변경 감지
- BigQuery의 Information Schema를 활용한 변경 감지
- Cloud Functions + Pub/Sub를 통한 실시간 트리거 시스템
- Eventarc를 통한 BigQuery 테이블 변경 이벤트 구독

```python
# schema_change_detector.py
from google.cloud import bigquery
from google.cloud import pubsub_v1

def detect_schema_changes():
    """Information Schema를 통한 스키마 변경 감지"""
    client = bigquery.Client()
    
    query = f"""
    SELECT 
        table_name,
        column_name,
        data_type,
        CURRENT_TIMESTAMP() as check_time
    FROM `{project_id}.test_dataset.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = 'events_20210131'
    ORDER BY ordinal_position
    """
    
    current_schema = list(client.query(query))
    
    # 이전 스키마와 비교하여 변경사항 감지
    if schema_changed(current_schema):
        trigger_metadata_update()
```

### 3. 예시 품질 개선
- 생성된 예시의 품질 평가 메트릭
- 사용자 피드백을 통한 예시 개선 루프