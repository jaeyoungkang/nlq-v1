# 데이터 분석 컨텍스트 인식 문제 분석 보고서

작성일: 2025-08-29

## 요약

- 증상: `data_analysis` 분류에서 분석이 이전 컨텍스트(특히 최근 쿼리 결과)를 충분히 반영하지 못함.
- 원인: 분석 프롬프트에 주입되는 `$context_blocks` 문자열이 메시지 텍스트만 요약하고, `execution_result.data`(쿼리 결과 행) 정보를 포함하지 않음.
- 조치: LLM 클라이언트에 분석 전용 컨텍스트 포맷터를 추가하여 최근 결과의 컬럼/샘플행을 함께 포함. 템플릿에 주입되는 컨텍스트를 데이터 친화적으로 개선.

## 재현 단계

1. 사용자 A가 `query_request`로 SQL을 실행하여 표 형태 결과를 반환(수십~수백 행).
2. 이어서 사용자 A가 "결과 분석해줘"와 같은 `data_analysis` 요청을 보냄.
3. 기대: 직전 쿼리의 주요 컬럼/상위 행을 참조한 분석 요약.
4. 실제: 이전 대화의 일반 텍스트만 참조하거나, "행 수만 인지"하고 구체 데이터 문맥 없이 분석함.

## 원인 분석

- 컨텍스트 구성 흐름 확인:
  - 조회: `routes/chat_routes.py:97` — BigQuery에서 최근 대화 로드 후 ContextBlock 리스트 생성.
  - 분석: `features/data_analysis/services.py:31-41` — `llm_client.analyze_data(question, context_blocks)` 호출.
  - LLM 입력 구성: `utils/llm_client.py:_execute_unified_prompting()`
    - 기존: `context_blocks_to_llm_format()` → `_normalize_conversation_context()` → `$context_blocks` 문자열 생성.
    - 문제: `_normalize_conversation_context()`는 메시지 `content`만 요약하고, `query_result_data`/`query_row_count`를 무시.

- 데이터 구조 확인:
  - `models/context.py`에서 assistant 메시지에 `query_result_data`(표 데이터)와 `query_row_count`가 포함되도록 변환.
  - 그러나 `_normalize_conversation_context()`에서 이 필드들을 사용하지 않아, 프롬프트가 데이터 표 내용을 잃음.

## 코드 변경 사항(해결)

- 파일: `utils/llm_client.py`
  - 함수 추가: `_format_analysis_context(context_messages)`
    - 최근 5개 메시지 범위에서 assistant의 결과가 있을 경우 컬럼(최대 3개)과 상위 2행 샘플을 포함하여 컨텍스트 문자열 구성.
    - 행 수(`query_row_count`)와 SQL 생성 여부 메타도 보강 노출.
  - 적용: `_execute_unified_prompting()`에서 `category == 'data_analysis'`일 때 `_normalize_conversation_context()` 대신 `_format_analysis_context()` 사용.

## 기대 효과

- 분석 프롬프트에 실제 데이터 샘플이 포함되어 LLM이 최근 결과의 구조와 값을 인지하고 설명/인사이트를 제공할 수 있음.
- 토큰 폭주 방지: 컬럼 3개, 샘플 2행 제한 및 최근 5개 메시지 제한 적용.

## 남은 고려사항 / 제안

- 결과 표가 매우 긴 경우 추가 요약(예: 수치형 컬럼의 간단 통계) 도입 고려.
- `routes/chat_routes.py:160` 저장 로직에서 `data_analysis`의 결과도 대화 테이블에 저장할지 정책 정의.
- 통계 API(`routes/system_routes.py`)는 현재 `message_type='user'/'assistant'`만 집계. 저장은 `complete` 타입을 사용하므로 집계 정의 일치 여부 검토 필요.
- 템플릿(`utils/prompts/data_analysis.json`)에서 `$context_blocks` 외에 별도 `$data_summary` 변수를 도입하면 컨텍스트·데이터를 구분해 더 명확한 프롬프트 구성이 가능.

## 참조 파일

- 컨텍스트 포맷터 추가: `utils/llm_client.py: _format_analysis_context`
- 분석 서비스: `features/data_analysis/services.py`
- 컨텍스트 변환: `models/context.py`
- 채팅 라우트(분기/저장): `routes/chat_routes.py`

