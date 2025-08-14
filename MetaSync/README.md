# MetaSync

**MetaSync**는 BigQuery 테이블의 스키마 정보와 Few-Shot 예시를 자동으로 수집하고 캐시하는 시스템입니다. Cloud Scheduler를 통해 주기적으로 실행되며, nlq-v1 시스템의 SQL 생성 품질 향상을 위한 메타데이터를 제공합니다.

## 🎯 주요 기능

- **자동 스키마 수집**: BigQuery 테이블의 최신 스키마 정보를 주기적으로 조회
- **예시 생성**: SQL 생성에 도움이 되는 Few-Shot 예시 제공
- **GCS 캐시**: 수집된 데이터를 Google Cloud Storage에 캐시하여 빠른 접근 제공
- **System B 연동**: nlq-v1 백엔드에서 캐시 데이터를 쉽게 활용할 수 있는 인터페이스

## 📁 프로젝트 구조

```
MetaSync/
├── README.md                    # 이 파일
├── cloud-functions/
│   └── metasync/
│       ├── main.py              # Cloud Function 메인 로직
│       ├── requirements.txt     # Python 의존성
│       └── .env.yaml           # 환경 변수 설정
└── (향후 확장 가능한 구조)
```

## 🚀 배포 방법

### 1단계: GCS 버킷 생성
```bash
gsutil mb -l asia-northeast3 gs://nlq-metadata-cache
```

### 2단계: Secret Manager에 API 키 저장 (선택적)
```bash
echo "your-anthropic-api-key" | gcloud secrets create anthropic-api-key --data-file=-
```

### 3단계: Cloud Function 배포
```bash
cd MetaSync/cloud-functions/metasync

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

### 4단계: Cloud Scheduler 설정
```bash
gcloud scheduler jobs create http metasync-scheduler \
  --location=asia-northeast3 \
  --schedule="0 17 * * *" \
  --time-zone="UTC" \
  --uri="https://asia-northeast3-nlq-ex.cloudfunctions.net/update-metadata-cache" \
  --http-method=POST \
  --description="Daily metadata cache update for MetaSync"
```

## 🧪 테스트 방법

### 로컬 테스트
```bash
cd MetaSync/cloud-functions/metasync

# Functions Framework로 로컬 실행
functions-framework --target=update_metadata_cache --port=8080

# 테스트 호출
curl -X POST http://localhost:8080
```

### GCP에서 테스트
```bash
# Cloud Function 직접 호출
gcloud functions call update-metadata-cache \
  --region=asia-northeast3 \
  --data='{}'

# Scheduler 수동 실행
gcloud scheduler jobs run metasync-scheduler --location=asia-northeast3

# 결과 확인
gsutil cat gs://nlq-metadata-cache/metadata_cache.json
```

## 💾 캐시 데이터 구조

GCS에 저장되는 캐시 데이터 형식:

```json
{
  "generated_at": "2024-01-15T17:00:00Z",
  "schema": {
    "table_id": "nlq-ex.test_dataset.events_20210131",
    "last_updated": "2024-01-15T17:00:00Z",
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
    }
  ]
}
```

## 🔗 System B 연동

nlq-v1 백엔드에서 MetaSync 캐시를 사용하는 방법:

```python
from backend.utils.metasync_cache_loader import get_metasync_cache_loader

# 캐시 로더 인스턴스 생성
cache_loader = get_metasync_cache_loader()

# 스키마 정보 조회
schema_info = cache_loader.get_schema_info()

# Few-Shot 예시 조회
examples = cache_loader.get_few_shot_examples()

# 컬럼 정보만 추출
columns = cache_loader.get_schema_columns()

# 캐시 상태 확인
is_available = cache_loader.is_cache_available()
metadata = cache_loader.get_cache_metadata()
```

## ⚙️ 환경 설정

### 환경 변수 (.env.yaml)
```yaml
GOOGLE_CLOUD_PROJECT: "nlq-ex"                           # GCP 프로젝트 ID
TARGET_TABLE_ID: "nlq-ex.test_dataset.events_20210131"   # 대상 BigQuery 테이블
GCS_BUCKET: "nlq-metadata-cache"                         # 캐시 저장 버킷
```

### 필요한 권한
Cloud Function이 실행되려면 다음 권한이 필요합니다:
- `roles/bigquery.dataViewer` - BigQuery 테이블 조회
- `roles/bigquery.metadataViewer` - 스키마 정보 조회
- `roles/storage.objectAdmin` - GCS 버킷 읽기/쓰기
- `roles/secretmanager.secretAccessor` - Secret Manager 접근 (선택적)

## 📊 모니터링

### Cloud Functions 로그 확인
```bash
gcloud functions logs read update-metadata-cache --region=asia-northeast3 --limit=50
```

### Scheduler 작업 상태 확인
```bash
gcloud scheduler jobs describe metasync-scheduler --location=asia-northeast3
```

### 캐시 파일 확인
```bash
# 캐시 파일 존재 확인
gsutil ls gs://nlq-metadata-cache/

# 캐시 내용 확인
gsutil cat gs://nlq-metadata-cache/metadata_cache.json | jq .
```

## 🔧 문제 해결

### 자주 발생하는 문제들

1. **권한 오류**
   ```
   # IAM 역할 확인
   gcloud projects get-iam-policy nlq-ex
   ```

2. **GCS 버킷 접근 오류**
   ```bash
   # 버킷 존재 확인
   gsutil ls gs://nlq-metadata-cache/
   ```

3. **BigQuery 테이블 접근 오류**
   ```bash
   # 테이블 존재 확인
   bq show nlq-ex:test_dataset.events_20210131
   ```

4. **함수 실행 시간 초과**
   - timeout을 늘리거나 메모리를 증가시킵니다
   ```bash
   gcloud functions deploy update-metadata-cache --timeout=540s --memory=1GiB
   ```

## 🚦 실행 주기

- **기본 실행 주기**: 매일 오전 2시 (KST) = UTC 17시
- **캐시 만료 시간**: 24시간
- **메모리 캐시 갱신**: 1시간 (System B에서)

## 📈 향후 개선 계획

- [ ] LLM API 연동으로 동적 예시 생성
- [ ] 다중 테이블 지원
- [ ] 백업 및 버전 관리
- [ ] 품질 메트릭 수집
- [ ] 알림 시스템 구축

## 🤝 기여 방법

1. 기능 개선이나 버그 수정 시 이슈 생성
2. 코드 변경 후 테스트 실행
3. README.md 업데이트 (필요시)

---

**MetaSync**는 nlq-v1 시스템의 핵심 인프라스트럭처로, 안정적이고 정확한 SQL 생성을 위한 메타데이터를 제공합니다.