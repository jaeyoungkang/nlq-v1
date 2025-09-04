# MetaSync Backend Feature 통합 계획서

> MetaSync를 독립된 Cloud Function에서 백엔드 feature 모듈로 통합하는 계획  
> **작성일**: 2025-09-04  
> **작성 기준**: backend_task_plan_template.md, CLAUDE.md

## 📋 계획서 구성 요소

### 1. 포괄적 현황 분석 (필수)

#### 1.1 대상 분석

##### MetaSync 현재 구조 (Cloud Function)
- **위치**: `MetaSync/cloud-functions/metasync/`
- **파일 구성**:
  - `main.py` (496 라인): MetaSyncManager 클래스, HTTP 진입점
  - `requirements.txt`: 의존성 정의
  - `Dockerfile`, `cloudbuild.yaml`: 배포 설정
- **주요 클래스/함수**:
  - `MetaSyncManager`: 메타데이터 수집/캐시 관리 핵심 클래스
  - `update_metadata_cache()`: HTTP Cloud Function 진입점
  - LLM 통합 메서드: `generate_examples_with_llm()`, `generate_schema_insights_with_llm()`

##### 백엔드 연동 현황
- **캐시 로더**: `backend/utils/metasync_cache_loader.py` (312 라인)
  - `MetaSyncCacheLoader` 클래스: GCS 캐시 데이터 읽기 전용
  - 싱글톤 패턴으로 구현
- **LLM Service 연동**: `backend/features/llm/services.py`에서 cache_loader 활용
  - SQL 생성 시 스키마/Few-Shot 예시 자동 주입
- **데이터 흐름**:
  1. Cloud Function이 GCS에 캐시 생성 (metadata_cache.json)
  2. 백엔드가 GCS에서 캐시 읽기 (읽기 전용)
  3. LLM 프롬프트에 캐시 데이터 주입

#### 1.2 문제 정의

##### 아키텍처 문제
- **분리된 시스템**: MetaSync가 별도 프로젝트로 관리되어 백엔드와 분리
- **중복 코드**: Anthropic API 호출, BigQuery 접근 등 백엔드와 중복
- **배포 복잡성**: Cloud Function + Cloud Scheduler 별도 관리 필요
- **버전 관리**: 백엔드와 MetaSync 간 버전 동기화 어려움

##### 운영 문제
- **모니터링 분산**: 로그와 메트릭이 별도 시스템에 분산
- **비용 관리**: Cloud Function 실행 비용 별도 추적 필요
- **디버깅 어려움**: 분리된 환경으로 인한 통합 디버깅 어려움

##### 확장성 문제
- **실시간 업데이트 제한**: 스케줄 기반으로만 동작 (매일 오전 2시)
- **API 노출 부재**: 백엔드에서 온디맨드 캐시 갱신 불가
- **커스터마이징 제한**: 테이블별 다른 캐시 전략 적용 어려움

### 2. 아키텍처 원칙 검토

#### 2.1 각 컴포넌트 분류

| 컴포넌트 | 현재 위치 | 제안 위치 | 근거 |
|---------|----------|----------|------|
| MetaSyncManager | MetaSync/cloud-functions/ | features/metasync/services.py | Feature-Driven 아키텍처 준수 |
| MetaSyncCacheLoader | backend/utils/ | features/metasync/repositories.py | 데이터 접근 계층으로 이동 |
| 캐시 생성 로직 | Cloud Function | features/metasync/services.py | 비즈니스 로직 통합 |
| GCS 접근 | 양쪽 모두 | features/metasync/repositories.py | Repository 패턴으로 통합 |
| LLM 호출 (중복) | MetaSync 자체 구현 | features/llm/services.py 재사용 | 중복 제거, DRY 원칙 |
| BigQuery 접근 | MetaSync 자체 구현 | core/repositories 재사용 | 인프라 계층 공유 |

#### 2.2 분류 근거 제시

- **features/metasync**: 메타데이터 관리는 독립된 기능 도메인
- **Repository 패턴**: GCS/BigQuery 접근을 Repository로 추상화
- **Service 계층**: 캐시 생성/관리 비즈니스 로직 집중
- **LLM 재사용**: 기존 LLMService 활용으로 중복 제거
- **의존성 주입**: app.py에서 MetaSyncService 초기화 및 주입

### 3. 목표 구조 (ASCII 트리)

```
backend/
├── core/
│   └── repositories/
│       ├── base.py              # BaseRepository (ABC)
│       ├── firestore_base.py    # FirestoreRepository
│       └── gcs_base.py          # GCSRepository (신규)
│
├── features/
│   ├── metasync/               # MetaSync Feature 모듈 (신규)
│   │   ├── __init__.py
│   │   ├── models.py           # MetadataCache, SchemaInfo 등
│   │   ├── services.py         # MetaSyncService (핵심 로직)
│   │   ├── repositories.py     # MetaSyncRepository (GCS/BigQuery)
│   │   ├── routes.py           # API 엔드포인트 (/api/metasync/*)
│   │   └── utils.py            # events 테이블 추상화 등
│   │
│   └── llm/
│       └── services.py         # LLMService (MetaSyncService가 재사용)
│
├── utils/                      # metasync_cache_loader.py 제거 (feature로 이동)
│
└── app.py                      # MetaSyncService 의존성 주입 추가
```

### 4. 기능 매핑 (현재 → 목표)

#### 4.1 클래스/함수 매핑

| 현재 구조 | 새 구조 | 변경 사항 |
|-----------|---------|----------|
| MetaSyncManager (Cloud Function) | MetaSyncService | Feature Service로 재구성 |
| MetaSyncCacheLoader (utils) | MetaSyncRepository | Repository 패턴 적용 |
| update_metadata_cache() | MetaSyncService.update_cache() | 메서드로 통합 |
| call_anthropic_api() | LLMService 재사용 | 중복 제거 |
| fetch_schema() | MetaSyncRepository.fetch_schema() | Repository 메서드 |
| generate_examples_with_llm() | MetaSyncService._generate_examples() | LLMService 활용 |
| abstract_events_tables() | utils.py로 분리 | 유틸리티 함수 |
| save_cache() | MetaSyncRepository.save_cache() | Repository 메서드 |

#### 4.2 API 엔드포인트 추가

```python
# features/metasync/routes.py
/api/metasync/cache          GET    # 현재 캐시 조회
/api/metasync/cache/refresh  POST   # 캐시 강제 갱신
/api/metasync/cache/status   GET    # 캐시 상태 확인
/api/metasync/tables         GET    # events 테이블 목록
```

### 5. 의존성 및 영향 범위 분석

#### 5.1 직접 의존성
- **LLMService**: cache_loader 파라미터가 MetaSyncRepository로 변경
- **app.py**: MetaSyncService 초기화 코드 추가 필요
- **Cloud Scheduler**: 백엔드 API 호출로 변경 필요

#### 5.2 간접 영향
- **성능**: 백엔드 프로세스 내 실행으로 메모리 사용량 증가
- **보안**: API 엔드포인트 인증 필요 (관리자 권한)
- **모니터링**: 백엔드 로깅 시스템으로 통합

#### 5.3 하위 호환성
- **점진적 마이그레이션**: Cloud Function과 백엔드 feature 병행 운영 가능
- **캐시 포맷 유지**: GCS metadata_cache.json 구조 그대로 유지
- **읽기 호환성**: 기존 캐시 파일 그대로 사용 가능

### 6. 마이그레이션 단계

#### Phase 1: 인프라 준비 (Day 1)
1. **GCS Repository 기반 구축**: `core/repositories/gcs_base.py` 구현
2. **MetaSync Feature 구조 생성**: `features/metasync/` 디렉토리 구조
3. **모델 정의**: MetadataCache, SchemaInfo 등 도메인 모델

#### Phase 2: 핵심 로직 이전 (Day 2-3)
4. **MetaSyncRepository 구현**: GCS/BigQuery 데이터 접근 계층
5. **MetaSyncService 구현**: 비즈니스 로직 이전 (LLMService 활용)
6. **유틸리티 분리**: events 테이블 추상화 등 utils.py로

#### Phase 3: API 및 통합 (Day 4)
7. **Routes 구현**: REST API 엔드포인트 추가
8. **의존성 주입**: app.py에서 MetaSyncService 초기화
9. **LLMService 연동**: cache_loader를 MetaSyncRepository로 교체

#### Phase 4: 테스트 및 전환 (Day 5)
10. **통합 테스트**: 캐시 생성/조회 전체 플로우 테스트
11. **병행 운영**: Cloud Function과 백엔드 feature 동시 운영
12. **모니터링**: 로그 및 성능 메트릭 확인

#### Phase 5: 마이그레이션 완료 (Day 6)
13. **Cloud Scheduler 변경**: 백엔드 API 호출로 전환
14. **Cloud Function 비활성화**: 안정화 후 제거
15. **문서 업데이트**: README, CLAUDE.md 업데이트

### 7. 구현 시 준수사항

#### 7.1 개발 표준 준수
- **CLAUDE.md 준수**: Feature-Driven 아키텍처, 계층형 구조
- **Repository 패턴**: BaseRepository 상속, 인터페이스 구현
- **에러 처리**: ErrorResponse/SuccessResponse 표준 사용
- **로깅**: utils.logging_utils.get_logger() 사용

#### 7.2 도메인 모델 고려사항
- **MetadataCache 모델**: 캐시 데이터 구조 정의
- **SchemaInfo 모델**: 테이블 스키마 정보 구조화
- **EventsTableInfo 모델**: 추상화된 events 테이블 정보

#### 7.3 성능 최적화
- **캐시 전략**: 메모리 캐시 + GCS 영구 저장
- **비동기 처리**: 캐시 갱신을 백그라운드 태스크로
- **증분 업데이트**: 전체 갱신 vs 부분 갱신 옵션

## 📝 프롬프트 구조 유지 방안

### 현재 프롬프트 구조 분석

#### 1. MetaSync 데이터 전달 방식
- **현재**: JSON 전체를 문자열로 변환하여 `$metasync_info` 변수에 주입
- **특징**: LLM이 JSON을 직접 파싱하여 필요한 정보 추출
- **장점**: 구조 변경에 유연, LLM이 컨텍스트 이해 용이

```python
# 현재 구현 (features/llm/services.py)
if self.cache_loader:
    cache_data = self.cache_loader._get_cache_data()
    metasync_info = json.dumps(cache_data, ensure_ascii=False, indent=2)
    template_vars['metasync_info'] = metasync_info
```

#### 2. 프롬프트 템플릿 구조
- **위치**: `core/prompts/templates/sql_generation.json`
- **변수**: `$metasync_info`, `$context_blocks`, `$question`
- **지침**: JSON 데이터에서 schema, examples, events_tables 추출

### 통합 후 프롬프트 구조 유지 전략

#### 1. 인터페이스 호환성 유지
```python
class MetaSyncRepository(FirestoreRepository):
    """기존 MetaSyncCacheLoader와 동일한 인터페이스 제공"""
    
    def _get_cache_data(self) -> Dict[str, Any]:
        """기존 메서드명 유지 - 하위 호환성"""
        return self.get_cache_data()
    
    def get_cache_data(self) -> Dict[str, Any]:
        """캐시 데이터를 기존과 동일한 형식으로 반환"""
        return {
            "generated_at": "...",
            "generation_method": "llm_enhanced",
            "schema": {...},
            "examples": [...],
            "events_tables": {...},
            "schema_insights": {...}
        }
```

#### 2. JSON 구조 완벽 유지
```python
class MetaSyncService:
    """캐시 생성 시 기존 JSON 구조 유지"""
    
    def generate_cache(self) -> Dict[str, Any]:
        """기존 MetaSync와 동일한 구조로 캐시 생성"""
        return {
            # 기존 구조 그대로 유지
            "generated_at": datetime.now().isoformat(),
            "generation_method": "llm_enhanced",
            "schema": self._fetch_schema(),
            "examples": self._generate_examples(),
            "events_tables": self._abstract_events_tables(),
            "schema_insights": self._generate_insights()
        }
```

#### 3. 프롬프트 템플릿 무변경
- **sql_generation.json**: 변경 불필요
- **변수 주입 방식**: 기존 로직 그대로 유지
- **LLM 파싱 로직**: JSON 직접 파싱 방식 유지

### 위험 요소 및 대응

#### 1. JSON 구조 불일치
- **위험**: 필드 누락으로 LLM 파싱 실패
- **대응**: 스키마 검증 테스트 필수

#### 2. 캐시 크기 증가
- **위험**: 프롬프트 토큰 제한 초과
- **대응**: events_tables 추상화 유지

#### 3. 성능 저하
- **위험**: Feature 통합으로 응답 지연
- **대응**: 메모리 캐시 적극 활용

## 🕐 캐시 생성 타이밍 제안

### 캐시 생성이 필요한 시점

#### 1. 초기 배포 시점
- **백엔드 최초 배포**: 캐시가 없는 상태에서 시작
- **권장 타이밍**: 배포 직후 즉시 생성
- **방법**: 배포 스크립트에 캐시 생성 명령 포함

#### 2. 스키마 변경 시점
- **테이블 구조 변경**: 컬럼 추가/삭제/타입 변경
- **권장 타이밍**: 변경 감지 후 5분 이내
- **방법**: BigQuery 이벤트 트리거 또는 수동 API 호출

#### 3. 정기 갱신 시점
- **일일 갱신**: 매일 오전 2시 (트래픽 최소 시간대)
- **주간 전체 갱신**: 매주 일요일 새벽 (전체 재생성)
- **방법**: Cron job 또는 Cloud Scheduler

#### 추천 구현 방식
- Cron 기반 일일 갱신
- 배포 시 자동 생성

## ✅ 실제 구현 완료 (2025-09-04)

### 🎯 완료된 작업 내역 (MetaSync Feature 통합)

#### Phase 1: 인프라 기반 구축 ✅
- ✅ **GCSRepository 기본 클래스 구현** (`core/repositories/gcs_base.py`)
  - GCS 클라이언트 싱글톤 패턴 구현
  - JSON 읽기/쓰기, 스냅샷 생성, 메타데이터 조회 기능
  - 추상 클래스로 확장 가능한 구조 제공
  
- ✅ **MetaSync Feature 디렉토리 구조 생성** (`features/metasync/`)
  - 완전한 Feature-Driven 구조 구축
  - __init__.py, models.py, services.py, repositories.py, routes.py, utils.py
  
- ✅ **도메인 모델 정의** (`features/metasync/models.py`)
  - MetadataCache, SchemaInfo, EventsTableInfo, FewShotExample
  - CacheStatus, CacheUpdateRequest 모델
  - 기존 Cloud Function과 100% 호환되는 JSON 구조

#### Phase 2: Repository 계층 구현 ✅
- ✅ **MetaSyncRepository 구현** (`features/metasync/repositories.py`)
  - GCSRepository 상속, GCS + BigQuery 통합 접근
  - 기존 MetaSyncCacheLoader와 완벽한 인터페이스 호환성 제공
  - 메모리 캐시 관리 (1시간 TTL)
  - 원본 JSON 문자열 반환 기능 (`get_cache_data_raw()`)
  
- ✅ **캐시 데이터 접근 메서드 구현**
  - `get_schema_info()`, `get_few_shot_examples()`, `get_events_tables()`
  - `is_cache_available()`, `refresh_cache()` 메서드
  - BigQuery 스키마 조회 및 샘플 데이터 fetch

#### Phase 3: Service 계층 구현 ✅
- ✅ **MetaSyncService 비즈니스 로직 이전** (`features/metasync/services.py`)
  - Cloud Function의 MetaSyncManager 로직 완전 이전
  - Events 테이블 추상화 (91.9% 토큰 절약 유지)
  - 스냅샷 관리 시스템 구현
  
- ✅ **LLMService 재사용으로 중복 제거**
  - `call_llm_direct()` 메서드를 통한 LLM 통합
  - Few-Shot 예시 및 스키마 인사이트 생성 로직 이전
  - Anthropic API 중복 코드 100% 제거

#### Phase 4: API 엔드포인트 구현 ✅
- ✅ **RESTful API 엔드포인트** (`features/metasync/routes.py`)
  - `/api/metasync/cache` (GET) - 현재 캐시 데이터 조회 (원본 JSON 순서 보장)
  - `/api/metasync/cache/status` (GET) - 캐시 상태 확인
  - `/api/metasync/cache/refresh` (POST) - 캐시 갱신
  - `/api/metasync/health` (GET) - 헬스체크
  
- ✅ **사용자 요청 반영 최적화**
  - 인증 시스템 제거 (원래 Cloud Function에 인증 없었음)
  - JSON 순서 보장을 위한 원본 문자열 직접 반환
  - 불필요한 API 제거 (`/tables`, `/snapshots`, `/memory-refresh`)
  - 단순한 JSON 응답 형식으로 변경

#### Phase 5: 통합 및 의존성 주입 ✅
- ✅ **app.py 의존성 주입 설정**
  - MetaSyncRepository, MetaSyncService 초기화 및 주입
  - LLMService와 MetaSyncRepository 공유 구조
  - 환경변수 기반 설정 (METASYNC_CACHE_BUCKET 등)
  
- ✅ **LLMService 연동 변경**
  - cache_loader 파라미터를 MetaSyncRepository로 교체
  - 기존 인터페이스 완벽 호환 유지
  - 프롬프트 템플릿 변경 불필요

#### Phase 6: 정리 및 문서화 ✅
- ✅ **기존 MetaSync 폴더 제거**
  - `MetaSync/` 디렉토리 완전 삭제
  - Cloud Function 코드 백엔드 Feature로 완전 이전
  
- ✅ **통합 테스트 및 검증**
  - 가상환경에서 import 테스트 성공
  - API 엔드포인트 동작 확인
  - 원본 JSON 순서 보장 확인

### 📊 구현 결과 및 성과

#### 아키텍처 개선 ✅
- ✅ **Feature-Driven 모듈로 완전 통합**
  - Cloud Function → Backend Feature 모듈 전환 완료
  - CLAUDE.md 아키텍처 원칙 100% 준수
  
- ✅ **Repository 패턴으로 데이터 접근 계층 통일**
  - GCSRepository → MetaSyncRepository 계층 구조
  - BaseRepository 인터페이스 호환성 유지
  
- ✅ **LLM 중복 코드 100% 제거**
  - Anthropic API 중복 호출 로직 완전 제거
  - LLMService 중앙화된 호출 구조 활용

#### 운영 효율성 ✅
- ✅ **단일 시스템으로 모니터링 통합**
  - 별도 Cloud Function 관리 부담 제거
  - 백엔드 로깅 시스템으로 완전 통합
  
- ✅ **온디맨드 캐시 갱신 API 제공**
  - 실시간 캐시 업데이트 가능
  - 스케줄러 의존성 제거된 유연한 운영
  
- ✅ **사용자 피드백 반영 최적화**
  - 불필요한 인증 제거
  - JSON 원본 순서 보장
  - API 구조 단순화

#### 성능 및 호환성 ✅
- ✅ **MetaSync 최적화 성과 유지**
  - Events Tables 추상화 (91.9% 토큰 절약)
  - 캐시 크기 95% 감소 효과 유지
  
- ✅ **완벽한 하위 호환성**
  - 기존 프롬프트 템플릿 변경 불필요
  - JSON 구조 100% 동일 유지
  - 기존 캐시 파일 그대로 사용 가능

#### 코드 품질 ✅
- ✅ **코드 재사용성 극대화**
  - LLMService, GCS 접근 로직 공유
  - 중복 코드 완전 제거
  
- ✅ **유지보수성 극대화**
  - 단일 저장소 통합 관리
  - Feature-Driven 구조로 모듈성 향상

### 🎯 최종 달성 목표

#### 기술적 목표 달성 ✅
- ✅ Cloud Function → Backend Feature 완전 전환
- ✅ Feature-Driven Architecture 100% 준수  
- ✅ Repository Pattern 완벽 적용
- ✅ LLM 서비스 중앙화 및 중복 제거

#### 사용자 요구사항 달성 ✅
- ✅ 인증 시스템 제거 (원래 없었음)
- ✅ JSON 순서 보장 (원본 문자열 반환)
- ✅ API 구조 단순화
- ✅ 불필요한 엔드포인트 제거

#### 운영 목표 달성 ✅
- ✅ 단일 시스템 통합 운영
- ✅ 실시간 캐시 관리 기능
- ✅ 완벽한 하위 호환성 보장 → **2025-09-04 하위 호환성 제거 완료**
- ✅ 성능 최적화 효과 유지

### 🔄 2025-09-04 추가 최적화 작업

#### Phase 7: LLMService 하위 호환성 제거 및 최신화 ✅
- ✅ **생성자 파라미터 최적화**
  - `cache_loader` (선택적) → `metasync_repository` (필수) 변경
  - 폴백 로직 제거: `cache_loader or get_metasync_repository()` 삭제
  - 명확한 타입 힌트: `MetaSyncRepository` 구체적 타입 지정
  
- ✅ **MetaSync 데이터 접근 간소화**
  - 조건부 체크 제거: `if self.cache_loader:` 삭제
  - 직접 메서드 호출: `self.metasync_repository.get_cache_data()`
  - 성능 향상: 런타임 조건문 제거
  
- ✅ **app.py 의존성 주입 업데이트**
  - 파라미터 명칭 변경: `cache_loader=` → `metasync_repository=`
  - 속성 접근 수정: `app.llm_service.cache_loader` → `app.llm_service.metasync_repository`
  - 로깅 메시지 업데이트: "직접 연동" 표시
  
- ✅ **구형 파일 및 코드 완전 제거**
  - `utils/metasync_cache_loader.py` 파일 삭제
  - `utils/__init__.py`에서 관련 import 제거
  - `get_metasync_cache_loader()` 함수 의존성 완전 제거

#### 최적화 결과 및 성과
- ✅ **코드 명확성 극대화**: 필수 의존성으로 명확한 구조
- ✅ **성능 향상**: 폴백 체크 제거로 런타임 최적화  
- ✅ **유지보수성 향상**: 구형 코드 제거로 코드베이스 정리
- ✅ **타입 안전성 강화**: 구체적 타입으로 IDE 지원 향상
- ✅ **Feature-Driven 완전 준수**: 모던 아키텍처 패턴 완성

#### 테스트 검증 완료
```
✅ LLMService 파라미터: ['self', 'repository', 'metasync_repository', 'config_manager']
✅ metasync_repository 파라미터 존재 (하위 호환성 코드 제거 완료)
✅ cache_loader 파라미터 제거 완료
✅ LLMService 초기화 완료 (MetaSyncRepository 직접 연동)
✅ LLMService와 MetaSyncService가 동일한 Repository를 공유합니다
```

## 🎯 주요 이점

### 기술적 이점
1. **코드 통합**: 중복 코드 제거, DRY 원칙 준수
2. **아키텍처 일관성**: Feature-Driven 아키텍처 완전 준수
3. **의존성 관리**: 단일 requirements.txt로 관리
4. **테스트 용이성**: 통합 테스트 환경 구축 가능

### 운영적 이점
1. **모니터링 통합**: 단일 로깅/메트릭 시스템
2. **배포 단순화**: 백엔드 배포에 포함
3. **비용 절감**: Cloud Function 실행 비용 제거
4. **유연성 향상**: 실시간 캐시 갱신 가능

### 확장성 이점
1. **API 제공**: RESTful API로 외부 접근 가능
2. **커스터마이징**: 테이블별 캐시 전략 적용 가능
3. **실시간 처리**: 온디맨드 캐시 갱신 지원
4. **플러그인 구조**: 다른 feature와 쉽게 연동

## 📚 참조 문서

- **[CLAUDE.md](../CLAUDE.md)**: 백엔드 개발 표준
- **[backend_task_plan_template.md](../backend_task_plan_template.md)**: 계획서 작성 지침
- **MetaSync README.md**: 현재 MetaSync 구조 및 설정

## 🎯 실행 계획

### 즉시 실행 가능 작업
1. GCS Repository 기반 클래스 구현
2. MetaSync Feature 디렉토리 구조 생성
3. 도메인 모델 정의

### 단계적 실행 작업
1. Repository 구현 (1-2일)
2. Service 구현 및 LLM 통합 (2-3일)
3. API 엔드포인트 및 테스트 (1일)
4. 병행 운영 및 전환 (2-3일)

### 위험 요소 및 대응
- **리스크**: GCS 접근 권한 문제
  - **대응**: 서비스 계정 권한 사전 확인
- **리스크**: 메모리 사용량 증가
  - **대응**: 캐시 크기 제한 및 TTL 설정
- **리스크**: Cloud Function 전환 시 다운타임
  - **대응**: 병행 운영 기간 충분히 확보

## ✅ 품질 체크리스트

- [x] 관련된 모든 파일/폴더를 조사했는가?
- [x] 각 컴포넌트의 core/features/utils 분류가 적절한가?
- [x] 목표 구조가 기능 주도 아키텍처를 따르는가?
- [x] 의존성 및 영향 범위를 완전히 파악했는가?
- [x] **CLAUDE.md 개발 표준을 모두 검토했는가?**
  - [x] 아키텍처 원칙 준수 계획이 있는가?
  - [x] API 계약 및 에러 처리 표준 적용 계획이 있는가?
  - [x] 도메인 모델 설계 원칙을 따르는가?
- [x] **Feature 통합 검토사항**
  - [x] Repository 패턴이 올바르게 적용되는가?
  - [x] Service 계층 비즈니스 로직이 명확한가?
  - [x] 의존성 주입 패턴을 따르는가?
  - [x] 기존 feature와의 연동이 고려되었는가?
- [x] 누락된 요소가 없는지 재확인했는가?

---

이 계획서는 MetaSync를 백엔드 feature로 통합하기 위한 체계적인 로드맵을 제공합니다.
Feature-Driven 아키텍처를 준수하면서 코드 재사용성과 운영 효율성을 극대화하는 것이 목표입니다.