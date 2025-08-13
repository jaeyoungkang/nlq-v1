# 테이블 스키마 정리 계획

## 1. 개요

본 문서는 `conversations`와 `query_results` 테이블의 스키마를 핵심 기능에 필수적인 요소만 남기고 단순화하는 정리 계획을 정의합니다. 이를 통해 데이터 모델의 명확성을 높이고, 유지보수 비용을 절감하며, 향후 기능 확장에 유연하게 대응하는 것을 목표로 합니다.

## 2. `conversations` 테이블 정리 계획

대화의 흐름과 AI의 SQL 생성 기록을 추적하는 데 필요한 최소한의 컬럼으로 구성합니다.

### 2.1 필수 컬럼 정의

| 컬럼명 | 필수 이유 |
| :--- | :--- |
| `conversation_id` | 전체 대화의 흐름을 묶는 그룹 ID. 컨텍스트 조회에 필수적입니다. |
| `message_id` | 각 메시지의 고유 식별자. 메시지 순서 보장 및 특정 메시지 참조에 사용됩니다. |
| `user_id` | 사용자를 식별하고 데이터 접근 권한을 제어하는 데 사용됩니다. |
| `message_type` | 메시지 발화자가 `user`인지 `assistant`인지 구분합니다. |
| `message` | 사용자와 AI가 주고받은 실제 메시지 내용입니다. |
| `timestamp` | 메시지 발생 시각. 대화 순서 정렬의 기준이 됩니다. |
| `generated_sql` | AI 어시스턴트가 생성한 SQL 쿼리. 시스템의 핵심 결과물입니다. |
| `query_id` | 생성된 SQL의 실행 결과를 `query_results` 테이블과 연결하는 외래 키(FK) 역할을 합니다. |

### 2.2 최종 스키마 (DDL)

```sql
-- 필수 컬럼으로 구성된 새로운 conversations 테이블 생성
CREATE TABLE `your_project.your_dataset.conversations` (
  conversation_id STRING NOT NULL,
  message_id STRING NOT NULL,
  user_id STRING NOT NULL,
  message_type STRING NOT NULL,
  message STRING,
  timestamp TIMESTAMP NOT NULL,
  generated_sql STRING,
  query_id STRING
);
```

## 3. `query_results` 테이블 정리 계획

SQL 실행 결과와 관련 메타데이터를 유연하게 저장하기 위해, 여러 컬럼 대신 단일 `payload` 컬럼을 사용하는 전략을 채택합니다.

### 3.1 필수 컬럼 정의

| 컬럼명 | 필수 이유 |
| :--- | :--- |
| `query_id` | `conversations` 테이블과 연결되는 고유 키(PK). 어떤 대화에서 발생한 결과인지 식별합니다. |
| `result_payload` | SQL 실행 결과 데이터와 모든 메타데이터(행 수, 데이터 크기, 스키마 정보 등)를 포함하는 JSON 객체. 스키마 변경 없이 유연한 정보 저장이 가능합니다. |
| `creation_time` | 결과가 생성된 시각. 데이터의 수명 관리(TTL) 및 디버깅에 사용됩니다. |

### 3.2 `result_payload` JSON 구조 예시

```json
{
  "status": "success",
  "metadata": { "row_count": 520, "data_size_kb": 128, "is_summary": true },
  "schema": [ {"name": "user_name", "type": "STRING"}, {"name": "order_count", "type": "INTEGER"} ],
  "data": [ /* 실제 데이터 배열 */ ]
}
```

### 3.3 최종 스키마 (DDL)

```sql
-- 필수 컬럼으로 구성된 새로운 query_results 테이블 생성
CREATE TABLE `your_project.your_dataset.query_results` (
  query_id STRING NOT NULL,
  result_payload STRING,
  creation_time TIMESTAMP NOT NULL
);
```

