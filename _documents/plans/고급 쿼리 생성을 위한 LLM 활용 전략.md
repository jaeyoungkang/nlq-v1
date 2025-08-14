## 🚀 고급 쿼리 생성을 위한 LLM 활용 전략

### 1\. 목표

  - **정확성 향상**: 동적으로 실제 스키마를 반영하고, 유효한 쿼리 예시(Few-Shot)를 제공하여 LLM이 존재하지 않는 컬럼을 참조하는 문제를 근본적으로 해결합니다.
  - **성능 최적화**: 매번 API 호출 시 스키마를 조회하는 대신, 주기적으로 업데이트되는 \*\*캐시(Cache)\*\*를 참조하여 응답 속도를 향상시킵니다.
  - **코드 단순화**: 복잡한 조건 분기 대신, LLM의 자가 수정 능력을 활용한 간결한 검증 및 재시도 로직을 구현합니다.
  - **자동화 및 확장성**: 스키마 변경, 예시 추가 등의 작업을 별도의 LLM 기반 시스템이 자동으로 처리하여 유지보수 비용을 줄이고 확장성을 높입니다.

### 2\. 아키텍처 설계: 2-System 모델

#### **System A: 메타데이터 관리 시스템 (주기적 실행)**

  - **역할**: BigQuery 스키마를 주기적으로 조회하고, LLM을 활용해 SQL 생성에 필요한 핵심 정보(메타데이터 및 예시)를 가공하여 **캐시 파일(예: `metadata_cache.json`)** 에 저장합니다.
  - **실행 주기**: 1일 1회 또는 테이블 스키마 변경 시 트리거.
  - **주요 기능**:
    1.  **동적 스키마 조회**: BigQuery에 연결하여 `nlq-ex.test_dataset.events_20210131` 테이블의 최신 스키마(컬럼명, 데이터 타입)를 가져옵니다.
    2.  **LLM 기반 Few-Shot 예시 생성**: 조회된 스키마를 기반으로, LLM에게 **"이 스키마를 바탕으로 유용하고 다양한 질문과 그에 맞는 BigQuery SQL 쿼리 예시 5개를 생성해줘"** 라고 요청하여 고품질의 예시를 자동으로 생성합니다.
    3.  **캐시 생성**: 조회된 스키마 정보와 생성된 Few-Shot 예시를 `metadata_cache.json` 파일로 저장합니다.

#### **System B: NLQ 애플리케이션 (실시간 사용자 요청 처리)**

  - **역할**: 사용자의 자연어 질문을 받아 SQL을 생성하고 실행합니다. 스키마 정보는 항상 **로컬 캐시 파일**을 참조합니다.
  - **주요 기능**:
    1.  **캐시된 메타데이터 로드**: `llm_client.py`가 시작될 때 `metadata_cache.json` 파일을 읽어 스키마와 Few-Shot 예시를 메모리에 로드합니다.
    2.  **강화된 프롬프트 구성**: 로드된 최신 스키마와 Few-Shot 예시를 `sql_generation.json` 프롬프트 템플릿에 동적으로 주입합니다.
    3.  **간결한 쿼리 유효성 검사 및 자가 수정**:
          * LLM이 1차로 SQL을 생성합니다.
          * BigQuery의 `dry_run` 기능을 사용해 쿼리의 유효성을 검사합니다 (`query_service.py`에 `validate_query(sql)` 함수 구현).
          * 유효성 검사에 실패하면(예: "Column not found"), **오류 메시지를 포함하여 LLM에게 "이 오류를 수정해서 다시 생성해줘"라고 한 번 더 요청**합니다.
          * 두 번째 시도도 실패하면, 사용자에게 "쿼리 생성에 실패했습니다." 라는 메시지를 반환합니다.

### 3\. 업데이트된 구현 계획

#### **`llm_client.py` - SQL 생성 로직 (수정)**

```python
# _execute_unified_prompting 또는 generate_sql 메서드 내

# 1. 캐시된 메타데이터 로드 (애플리케이션 시작 시 1회)
# self.schema_info = load_schema_from_cache()
# self.few_shot_examples = load_examples_from_cache()

# 2. 프롬프트에 동적 정보 주입
system_prompt = prompt_manager.get_prompt(
    'sql_generation',
    'system_prompt',
    schema_info=self.schema_info,
    few_shot_examples=self.few_shot_examples,
    # ... 기타 변수
)
# ... LLM 1차 호출 ...
generated_sql_1 = self._call_llm(system_prompt, user_prompt)

# 3. 쿼리 유효성 검사
validation_result = bigquery_client.validate_query(generated_sql_1)

if not validation_result['valid']:
    # 4. 자가 수정 요청
    correction_prompt = f"다음 쿼리에서 오류가 발생했습니다. 오류 메시지를 참고하여 쿼리를 수정해주세요.\n\n오류: {validation_result['error']}\n\n기존 쿼리:\n{generated_sql_1}"
    
    # LLM 2차 호출 (수정 요청)
    generated_sql_2 = self._call_llm(system_prompt, correction_prompt)
    
    # 최종 쿼리로 사용
    final_sql = generated_sql_2
else:
    final_sql = generated_sql_1

return {"success": True, "sql": final_sql}
```

#### **`query_service.py` - 쿼리 유효성 검사 함수 (신규)**

```python
# backend/utils/bigquery/query_service.py 내에 추가

def validate_query(self, sql_query: str) -> Dict[str, Any]:
    """BigQuery dry run으로 쿼리 유효성을 검사합니다."""
    try:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        self.client.query(sql_query, job_config=job_config)
        return {"valid": True}
    except Exception as e:
        logger.warning(f"쿼리 유효성 검사 실패: {e}")
        return {"valid": False, "error": str(e)}
```

### 4\. 기대 효과

  * **유지보수**: 테이블 스키마가 변경되어도 메인 애플리케이션의 **코드 수정이 전혀 필요 없습니다.** 별도의 메타데이터 관리 시스템이 변경 사항을 자동으로 감지하고 캐시를 업데이트합니다.
  * **정확성**: LLM은 항상 최신 스키마 정보와 고품질의 예시를 바탕으로 쿼리를 생성하므로, 부정확한 컬럼을 사용하는 문제가 크게 줄어듭니다.
  * **안정성**: `dry_run`을 통한 자가 수정 로직은 LLM이 간혹 실수를 하더라도 시스템 자체적으로 문제를 해결할 수 있는 **회복탄력성**을 제공합니다.
  * **성능**: 매 요청마다 BigQuery 스키마를 조회하는 대신 로컬 캐시를 사용하므로, **SQL 생성 단계의 응답 속도가 빠릅니다.**