# 데이터 분석 컨텍스트 인식 문제 분석 보고서

작성일: 2025-08-29

## 요약

- 증상: `data_analysis` 분류에서 분석이 이전 컨텍스트(특히 최근 쿼리 결과)를 충분히 반영하지 못함.
- 원인: 분석 프롬프트에 주입되는 `$context_blocks` 문자열이 메시지 텍스트만 요약하고, `execution_result.data`(쿼리 결과 행) 정보를 포함하지 않음.
- 조치: LLM 클라이언트에 분석 전용 컨텍스트 포맷터를 추가하여 최근 결과의 컬럼/샘플행을 함께 포함. 템플릿에 주입되는 컨텍스트를 데이터 친화적으로 개선.

## 요구사항 변경: 가능한 한 Raw 데이터 전달

- 새로운 목표: 분석 단계에서 LLM이 최대한 풍부한 “원시 데이터”를 직접 참조할 수 있도록, 프롬프트에 더 많은 행/컬럼을 포함.
- 제약 고려: LLM 토큰 한도와 비용을 감안하여, 동적 예산 내에서 가능한 한 많은 데이터를 실어 보냄.

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

## Raw 데이터 확장 설계(권장)

- 1) 프롬프트 템플릿 확장
  - `utils/prompts/data_analysis.json`에 `$raw_data_json`(또는 `$data_json_chunk`) 변수를 추가.
  - user_prompt 예시: “컨텍스트: $context_blocks\nRAW 데이터(JSON): $raw_data_json\n질문: $question”

- 2) 동적 데이터 패킹 로직 추가
  - 위치: `utils/llm_client.py:_execute_unified_prompting()`의 data_analysis 분기.
  - 최근 쿼리 결과(`ContextBlock.execution_result.data`)를 1개 세트 기준으로 사용하되, 다음 규칙으로 최대한 많이 포함:
    - 행 제한: `ANALYSIS_MAX_ROWS`(기본 200)까지 포함, 토큰 예산 초과 시 줄임.
    - 문자 제한: `ANALYSIS_MAX_CHARS`(기본 60,000 chars) 내에서 잘라내기.
    - 컬럼 처리: 기본 “전체 컬럼” 포함, 초과 시 우선순위(수치/범주/시간형)로 정렬 후 상위 N개 유지.
    - 중첩/리스트 필드: 평탄화(키를 `a.b.c`로) 후 포함.
  - 결과 JSON은 LLM 파싱 안정성을 위해 pretty=False(압축) 문자열로 주입.

- 3) 토큰 예산 계산(개략)
  - 시스템/유저 프롬프트 고정 오버헤드 + 컨텍스트 텍스트 길이 + RAW JSON 길이 ≤ 모델 한도(예: 2000 tokens 내외)
  - 간이 추정: 1 token ≈ 4 chars 가정 → `ANALYSIS_MAX_CHARS` 동적 조정.

- 4) 보안/프라이버시
  - PII/민감정보 마스킹 훅 추가(옵션): 이메일/전화/주민등록번호 패턴 마스킹.
  - 환경변수 `ANALYSIS_PII_REDACTION=true`일 때만 활성화.

- 5) 실패 폴백
  - RAW JSON 생성 실패 또는 너무 큰 경우: 현재 방식(컬럼/샘플 2행)로 폴백.

## 제안 구현 스케치(의사코드)

```
# utils/llm_client.py
if category == 'data_analysis':
    normalized_context = self._format_analysis_context(llm_context)
    raw_rows = self._extract_latest_result_rows(context_blocks)
    raw_json = self._pack_rows_as_json(raw_rows,
        max_rows=int(os.getenv('ANALYSIS_MAX_ROWS', 200)),
        max_chars=int(os.getenv('ANALYSIS_MAX_CHARS', 60000)),
        pii_redaction=os.getenv('ANALYSIS_PII_REDACTION') == 'true')
    user_prompt = prompt_manager.get_prompt(
        category='data_analysis', template_name='user_prompt',
        context_blocks=normalized_context,
        raw_data_json=raw_json,
        question=question,
        fallback_prompt=...
    )
```

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
