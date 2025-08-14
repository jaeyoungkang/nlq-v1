# BigQuery 모듈 사용하지 않는 코드 정리 계획

## 개요
BigQuery 관련 모듈들에서 사용되지 않는 코드들을 식별하고 정리하는 포괄적인 계획입니다.

## 1. query_service.py 정리 사항

### 1.1 사용되지 않는 메서드 (제거 대상)

#### 메타데이터 관련 메서드들
- **`list_datasets()` (166-198행)**: 
  - 현재 프로젝트 어디에서도 호출되지 않음
  - UI에서도 데이터셋 탐색 기능 미구현
  - 기본 테이블 중심 운영으로 불필요

- **`list_tables()` (200-243행)**:
  - 현재 프로젝트 어디에서도 호출되지 않음
  - 테이블 탐색 기능 미구현
  - 기본 테이블(`nlq-ex.test_dataset.events_20210131`) 고정 사용

- **`get_table_schema()` (245-291행)**:
  - 현재 프로젝트 어디에서도 호출되지 않음
  - `get_default_table_metadata()`가 동일 역할 수행
  - 중복 기능으로 판단

#### 유틸리티 메서드
- **`format_bytes()` (336-349행)**:
  - 프로젝트 내 어디에서도 호출되지 않음
  - 통계 정보에서도 사용되지 않음
  - 바이트 포맷팅 기능 불필요

### 1.2 사용되지 않는 임포트 (정리 대상)

```python
# 수정 전:
from datetime import datetime, timezone
from typing import Dict, List, Any

# 수정 후:
from datetime import datetime
from typing import Dict, Any
```

- **`timezone`**: 코드 내에서 실제 사용되지 않음
- **`List`**: 현재 타입 힌트에서 사용되지 않음

### 1.3 유지해야 할 메서드

#### 핵심 메서드들 (현재 사용중)
- **`execute_query()`**: `chat_routes.py:98`에서 활발히 사용
- **`_extract_job_stats()`**: `execute_query()` 내부에서 사용

## 2. __init__.py (BigQueryClient) 정리 사항

### 2.1 사용되지 않는 노출 메서드 (제거 대상)

#### 현재 외부에서 호출되지 않는 메서드들
- **`validate_query()` (43-45행)**:
  - `__init__.py`에서 노출되지만 외부에서 호출되지 않음
  - **제거**: 현재 사용되지 않음

- **`get_default_table_metadata()` (47-49행)**:
  - `__init__.py`에서 노출되지만 외부에서 호출되지 않음
  - **제거**: 현재 사용되지 않음

- **`get_query_result()` (75-78행)**:
  - `__init__.py`에서 노출되지만 외부에서 호출되지 않음
  - **제거**: 현재 사용되지 않음

### 2.2 정상적으로 사용되는 메서드들

#### 쿼리 관련
- **`execute_query()`**: `chat_routes.py:98`에서 사용

#### 대화 관련
- **`save_conversation()`**: `chat_routes.py:74, 158`에서 사용
- **`get_user_conversations()`**: `chat_routes.py:192`에서 사용
- **`get_conversation_context()`**: `chat_routes.py:56`에서 사용
- **`get_latest_conversation()`**: `chat_routes.py:222`에서 사용
- **`save_query_result()`**: `chat_routes.py:101`에서 사용

#### 사용자 관리 관련
- **`check_user_access()`**: `auth_utils.py:320`에서 사용
- **`update_last_login()`**: `auth_utils.py:324`에서 사용
- **`get_user_stats()`**: `system_routes.py:147`, `app.py:82`에서 사용
- **`ensure_whitelist_table_exists()`**: `app.py:71`에서 사용

## 3. 종합 정리 계획

### 3.1 제거 대상 항목들

#### query_service.py에서 제거
```python
# 제거할 메서드들 (총 190라인 감소):
- validate_query() (118-164행) - 47라인
- list_datasets() (166-198행) - 33라인
- list_tables() (200-243행) - 44라인  
- get_table_schema() (245-291행) - 47라인
- get_default_table_metadata() (293-334행) - 42라인
- format_bytes() (336-349행) - 14라인

# 제거할 임포트:
- timezone (from datetime import)
- List (from typing import)
```

#### __init__.py에서 제거
```python
# 제거할 메서드:
- validate_query() (43-45행) - 3라인
- get_default_table_metadata() (47-49행) - 3라인
- get_query_result() (75-78행) - 4라인
```

### 3.2 예상 효과

#### 코드 감소량
- **query_service.py**: 370라인 → 180라인 (51% 감소)
- **__init__.py**: 98라인 → 88라인 (10% 감소)
- **총 감소**: 200라인

#### 유지보수성 향상
- 미사용 코드 제거로 코드 복잡도 감소
- 메타데이터 관련 기능 제거로 단순화
- 핵심 기능(쿼리 실행, 대화 관리, 사용자 관리)에 집중

## 4. 구현 단계

### 4.1 1단계: query_service.py 정리
1. 미사용 메서드 6개 제거
2. 미사용 임포트 정리
3. 코드 재정렬 및 최적화

### 4.2 2단계: __init__.py 정리
1. 미사용 노출 메서드 3개 제거
2. 관련 주석 업데이트

## 5. 주의사항

### 5.1 제거 원칙
- 현재 사용되지 않는 모든 코드 제거
- 향후 확장 고려 코드는 유지하지 않음
- 필요 시 새로 구현하는 방식 채택

### 5.2 하위 호환성
- 외부에서 직접 호출되는 메서드만 보존
- 사용되지 않는 API는 모두 제거

### 5.3 코드 품질
- 제거 후에도 에러 처리 로직 유지
- 로깅 및 모니터링 기능 보존
- 핵심 기능에만 집중된 깔끔한 구조 유지