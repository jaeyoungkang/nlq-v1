### **분류 카테고리 통합 및 LLM 중심 컨텍스트 처리 전환 계획**

#### **1. 목표**

  - **분류 단순화**: `follow_up_query`와 같은 복잡한 컨텍스트 기반 카테고리를 제거하고, **핵심 5개 카테고리 체제로 단순화**합니다.
  - **LLM 역할 강화**: 분류 단계의 부담을 줄이는 대신, **대화 맥락(Context)을 충실히 제공**하여 SQL 생성 및 분석 단계의 LLM이 직접 후속 질문 의도를 파악하고 처리하도록 역할을 강화합니다.
  - **유지보수성 극대화**: 조건 분기 로직을 최소화하여 코드의 복잡도를 낮추고 유지보수성을 향상시킵니다.

#### **2. 주요 변경 사항**

##### **1단계: 분류 프롬프트 단순화**

`backend/utils/prompts/classification.json` 파일의 `system_prompt`를 수정하여 컨텍스트 기반 확장 카테고리를 제거하고, 핵심 카테고리에만 집중하도록 변경합니다.

  - **수정 대상**: `system_prompt`의 `content`
  - **변경 내용**: `컨텍스트 기반 확장 카테고리` 섹션 전체 삭제

**수정 후 `system_prompt` 예시**

```json
{
  "content": "사용자 입력을 5개 핵심 카테고리로 분류하고 JSON으로 응답:\\n\\n**핵심 카테고리:**\\n1. **query_request** - BigQuery 데이터 조회 및 분석 요청 (후속 질문, 수정 요청 포함)\\n   - 예: \"상위 10개\", \"그 중에서 활성 사용자만\", \"날짜를 어제로 변경해서 다시 조회해줘\", \"결과 분석해줘\"\\n\\n2. **metadata_request** - 테이블/스키마 정보 요청\\n   - 예: \"테이블 구조\", \"컬럼 정보\"\\n\\n3. **guide_request** - 사용법/안내 요청\\n   - 예: \"사용법\", \"도움말\"\\n\\n4. **out_of_scope** - 기능 범위 외 일반 대화\\n   - 예: \"안녕\", \"고마워\"\\n\\nJSON 형식으로만 응답: {\"category\": \"분류\", \"confidence\": 0.95, \"reasoning\": \"이유\"}"
}
```

  * **핵심 변경**: `query_request`의 설명을 "후속 질문, 수정 요청 포함"으로 확장하고, `data_analysis`를 통합하여 **LLM의 판단 영역을 넓혀줍니다.**

-----

##### **2단계: 라우팅 로직 단순화**

`backend/routes/chat_routes.py`에서 분기 처리 로직을 대폭 단순화합니다.

  - **수정 대상**: `process_chat_stream` 함수 내 분류(category) 처리 부분
  - **변경 내용**: `follow_up_query`, `data_analysis` 등 제거된 카테고리에 대한 `elif` 블록을 모두 삭제하고, `query_request`와 `metadata_request` 중심으로 처리 로직을 통합합니다.

**수정 후 `chat_routes.py` 로직 흐름**

```python
# 1. 입력 분류
classification_result = llm_client.classify_input(message, conversation_context)
category = classification_result.get("classification", {}).get("category", "query_request")
logger.info(f"🏷️ [req_{request_id}] Classified as: {category}")

# 2. 분류에 따른 처리 (단순화된 분기)
if category in ["query_request", "metadata_request"]: # 쿼리/메타데이터 요청 통합 처리
    # LLM이 컨텍스트를 보고 SQL을 생성하거나 메타데이터 조회 쿼리를 생성
    yield create_sse_event('progress', {'stage': 'sql_generation', 'message': '📝 SQL 생성 중...'})
    sql_result = llm_client.generate_sql(message, bigquery_client.project_id, None, conversation_context)
    
    # ... (이하 SQL 실행 및 결과 반환 로직) ...

elif category == "guide_request":
    # 가이드 요청 처리
    # ...

else: # out_of_scope
    # 범위 외 요청 처리
    # ...
```

-----

##### **3단계: SQL 생성 프롬프트 강화**

분류기가 단순해진 만큼, `sql_generation.json`의 프롬프트가 대화 맥락을 더 잘 이해하고 후속 질문, 수정, 분석 요청을 처리할 수 있도록 역할을 강화해야 합니다.

  - **수정 대상**: `backend/utils/prompts/sql_generation.json`의 `system_prompt`
  - **변경 내용**: "이전 대화를 참고하여" 부분을 더 구체화하고, **데이터 분석 요청까지 처리**할 수 있다는 점을 명시합니다.

**수정 후 `sql_generation.json` `system_prompt` 예시**

```json
{
  "content": "당신은 BigQuery SQL 전문가이자 데이터 분석가입니다. 사용자의 자연어 질문을 정확하고 효율적인 BigQuery SQL로 변환해주세요.\\n\\n## 컨텍스트 처리 규칙\\n- **[이전 대화 없음]**인 경우: 독립적인 새 쿼리 생성\\n- **이전 대화가 있는 경우**: 이전 SQL 패턴, 필터 조건, 질문 의도를 파악하여 다음 중 하나를 수행하세요:\\n  1. **후속 질문**: 이전 쿼리 결과에 조건을 추가하거나(refinement) 확장하는(follow-up) 쿼리 생성\\n  2. **수정 요청**: 사용자의 수정 요구사항을 반영하여 기존 쿼리를 변경\\n  3. **비교 분석**: 이전 결과와 비교할 수 있는 새로운 쿼리 생성\\n  4. **데이터 분석**: 사용자가 '분석'이나 '해설'을 요청하면, 데이터를 요약하고 인사이트를 도출할 수 있는 집계(aggregation) 쿼리 생성\\n\\n## 출력 규칙\\n..."
}
```

#### **3. 기대 효과**

1.  **개발 단순성**: 새로운 컨텍스트 유형이 추가되어도 분류기와 라우팅 로직을 수정할 필요가 없어집니다. 프롬프트 수정만으로 대응이 가능합니다.
2.  **LLM 성능 극대화**: LLM이 가장 잘하는 '문맥 이해' 능력을 최대한 활용하여, 시스템의 지능을 LLM에 집중시킵니다.
3.  **유지보수 비용 감소**: 복잡한 분기문과 여러 프롬프트 파일을 관리할 필요가 없어 코드가 깔끔해지고 유지보수가 쉬워집니다.
4.  **확장성**: 향후 더 복잡한 대화 시나리오가 추가되더라도, SQL 생성 프롬프트만 강화하면 되므로 확장성이 뛰어납니다.

이 계획은 현재 시스템의 **'통합 프롬프팅 전략'을 한 단계 더 발전**시키는 방향이며, 시스템의 핵심 복잡도를 LLM으로 이전하여 전체 아키텍처를 더 견고하고 유연하게 만들 것입니다.

-----
나 : data_analysis 은 컨텍스트로 첨부된 데이터에 대해서 LLM이 의견을 주는기능이다.

정확한 지적 감사합니다. 제가 `data_analysis`의 핵심적인 역할을 잘못 이해했습니다.

사용자께서 말씀하신 대로 \*\*"`data_analysis`는 새로운 쿼리를 생성하는 것이 아니라, 이미 조회되어 컨텍스트로 첨부된 데이터에 대해 LLM이 의견을 주는 기능"\*\*이 맞습니다. 이 중요한 부분을 반영하여 계획을 수정하겠습니다.

이전 제안(모든 것을 `query_request`로 통합)은 `data_analysis`의 고유한 역할을 훼손할 수 있으므로 폐기하고, 아래와 같이 더 정확하고 안전한 **수정된 계획**을 제안합니다.

-----

### **수정된 계획: `data_analysis` 역할 유지를 통한 아키텍처 개선**

#### **1. 목표**

  - **분류 체계 유지**: `data_analysis`를 **별도의 카테고리로 유지**하여 "SQL 생성"과 "데이터 분석"이라는 두 가지 핵심 액션을 명확히 분리합니다.
  - **라우팅 로직 명확화**: `chat_routes.py`에서 `query_request`와 `data_analysis`를 위한 **별도의 처리 경로를 유지**하여, 각 요청이 올바른 서비스로 전달되도록 보장합니다.
  - **LLM 역할 최적화**: LLM에게 문맥에 따라 SQL을 생성하거나, 주어진 데이터를 분석하는 **두 가지 명확한 역할**을 부여하여 성능과 안정성을 높입니다.

#### **2. 수정된 구현 단계**

##### **1단계: 분류(Classification) 프롬프트 재수정**

`follow_up_query` 등은 `query_request`로 통합하되, **`data_analysis`는 독립적인 카테고리로 명확히 분리**합니다.

**수정할 파일:** `backend/utils/prompts/classification.json`

**수정 후 `system_prompt` 예시:**

```json
{
  "content": "사용자 입력을 5개 핵심 카테고리로 분류하고 JSON으로 응답:\\n\\n**핵심 카테고리:**\\n1. **query_request** - BigQuery 데이터 조회 요청 (후속 질문, 수정 요청 포함)\\n   - 예: \"상위 10개\", \"그 중에서 활성 사용자만\", \"날짜를 어제로 변경해서 다시 조회해줘\"\\n\\n2. **data_analysis** - **이미 조회된 결과**에 대한 분석, 요약, 해설 요청\\n   - 예: \"결과 분석해줘\", \"이 데이터 설명해줘\", \"인사이트가 뭐야?\"\\n\\n3. **metadata_request** - 테이블/스키마 정보 요청\\n   - 예: \"테이블 구조\", \"컬럼 정보\"\\n\\n4. **guide_request** - 사용법/안내 요청\\n\\n5. **out_of_scope** - 기능 범위 외 일반 대화\\n\\nJSON 형식으로만 응답: { ... }"
}
```

  * **핵심 변경**: `data_analysis`를 다시 독립시키고, "이미 조회된 결과에 대한"이라는 조건을 명확히 하여 LLM이 두 요청을 더 잘 구분하도록 돕습니다.

-----

##### **2단계: 라우팅(Routing) 로직 유지 및 개선**

`chat_routes.py`에서 `data_analysis`를 위한 `elif` 블록을 **유지하고, 컨텍스트에서 데이터를 추출하는 로직을 강화**합니다.

**수정할 파일:** `backend/routes/chat_routes.py`

**수정 후 로직 흐름:**

```python
# backend/routes/chat_routes.py

category = llm_client.classify_input(...)

if category == "query_request":
    # 📝 SQL 생성 로직: llm_client.generate_sql(...) 호출
    # ...

elif category == "data_analysis":
    # 📊 데이터 분석 로직 (SQL 생성 안 함)
    yield create_sse_event('progress', {'stage': 'analysis', 'message': '📊 데이터 분석 중...'})
    
    # 컨텍스트에서 이전 쿼리 결과(데이터)를 추출하는 로직
    previous_sql = None
    previous_data = None
    if conversation_context:
        for ctx_msg in reversed(conversation_context):
            if ctx_msg.get('query_result_data'): # 컨텍스트에 데이터가 있는지 확인
                previous_sql = ctx_msg.get('metadata', {}).get('generated_sql')
                previous_data = ctx_msg.get('query_result_data')
                logger.info(f"📊 [{request_id}] 컨텍스트에서 분석할 데이터 로드: {len(previous_data)}행")
                break
    
    # LLM의 분석 기능 호출
    analysis_result = llm_client.analyze_data(message, previous_data, previous_sql, conversation_context)
    
    # 분석 결과를 스트림으로 전송
    result = {"type": "analysis_result", "content": analysis_result.get("analysis", "분석 중 오류 발생")}

else:
    # 기타 요청 처리
    # ...
```

  * **핵심 변경**: `data_analysis` 분기를 유지하여, SQL 생성을 건너뛰고 컨텍스트의 데이터를 `analyze_data` 함수로 직접 전달합니다.

