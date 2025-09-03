# MetaSync 결과물 확인 가이드

## 📍 결과물 저장 위치

### 1. **Google Cloud Storage (주 저장소)**
```bash
# GCS 버킷 내용 확인
gcloud storage ls gs://nlq-metadata-cache/ --long

# JSON 파일 다운로드해서 확인
gcloud storage cp gs://nlq-metadata-cache/metadata_cache.json ./
cat metadata_cache.json | jq .

# 또는 브라우저에서 확인
# https://console.cloud.google.com/storage/browser/nlq-metadata-cache
```

### 2. **백엔드를 통한 확인**
```bash
cd /Users/jaeyoungkang/workspace/nlq-v1/backend
source venv/bin/activate

python3 -c "
from utils.metasync_cache_loader import get_metasync_cache_loader
cache_loader = get_metasync_cache_loader()

# 전체 데이터 확인
print('전체 캐시:', cache_loader._get_cache_data())

# 각 섹션별 확인
print('메타데이터:', cache_loader.get_cache_metadata())
print('예시:', cache_loader.get_few_shot_examples())
print('인사이트:', cache_loader.get_schema_insights())
print('테이블 목록:', cache_loader.get_events_tables())
"
```

## 📋 현재 캐시 상태

**현재 캐시 정보:**
- **생성일**: 2025-08-14T09:29:12.169051
- **생성 방법**: unknown (이전 버전)
- **LLM 강화**: ❌ False
- **Events 테이블**: 0개 (구버전)
- **스키마 인사이트**: ❌ 없음

**⚠️ 주의**: 현재 캐시는 간소화된 프롬프트가 적용되기 전의 이전 데이터입니다.

## 🔄 새 결과물 생성하기

### Cloud Function 수동 실행
```bash
# 1. Google Cloud 인증
gcloud auth login
gcloud config set project nlq-ex

# 2. MetaSync 함수 수동 실행
gcloud functions call update_metadata_cache \
  --region=asia-northeast3

# 3. 실행 결과 확인
gcloud functions logs read update_metadata_cache \
  --region=asia-northeast3 \
  --limit=50
```

### 로컬 테스트 (방금 실행한 것)
```bash
cd /Users/jaeyoungkang/workspace/nlq-v1/MetaSync
python3 test_metasync_local.py
```

## 📊 예상되는 새 결과물 구조

간소화된 프롬프트로 생성될 결과물:

```json
{
  "generated_at": "2025-09-03T...",
  "generation_method": "llm_enhanced",
  "schema": {
    "table_id": "nlq-ex.test_dataset.events_20210131",
    "columns": [...23개 컬럼...]
  },
  "examples": [
    {
      "question": "최근 100개의 이벤트 전체 조회",
      "sql": "SELECT * FROM `your_table` ORDER BY event_timestamp DESC LIMIT 100"
    },
    {
      "question": "날짜별 이벤트 발생 횟수 집계", 
      "sql": "SELECT DATE(TIMESTAMP_MICROS(event_timestamp)) as event_date, COUNT(*) as event_count FROM `your_table` GROUP BY 1 ORDER BY 1 DESC LIMIT 100"
    },
    {
      "question": "이벤트 타입별 사용자 분포 분석",
      "sql": "SELECT event_name, COUNT(DISTINCT user_id) as unique_users FROM `your_table` GROUP BY 1 ORDER BY 2 DESC LIMIT 100"
    }
  ],
  "events_tables": [
    "nlq-ex.test_dataset.events_20210131",
    "nlq-ex.test_dataset.events_20210201",
    "..."
  ],
  "schema_insights": {
    "purpose": "이벤트 로그 및 사용자 행동 분석 테이블",
    "key_columns": ["event_timestamp", "event_name", "user_id"],
    "analysis_tips": ["시간대별 이벤트 분포 분석", "사용자별 행동 패턴 추적"]
  }
}
```

## 🔍 결과물 품질 확인 포인트

### ✅ Few-Shot 예시 품질
- [ ] 3개 예시 생성 (기존 5개에서 감소)
- [ ] TIMESTAMP_MICROS() 함수 사용
- [ ] 모든 쿼리에 LIMIT 100 포함
- [ ] 실제 테이블명 반영

### ✅ 스키마 인사이트 품질  
- [ ] purpose 필드 존재
- [ ] key_columns 배열 존재
- [ ] analysis_tips 배열 존재
- [ ] 간결하고 실용적인 내용

### ✅ 시스템 효율성
- [ ] 토큰 사용량 70% 감소
- [ ] 응답 속도 개선
- [ ] API 비용 절약
- [ ] claude-3-5-haiku-20241022 모델 사용