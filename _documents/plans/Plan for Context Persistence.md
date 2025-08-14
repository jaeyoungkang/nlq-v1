# LLM과의 대화에서 이전 대화 기록 활용 구현 방안

## 현재 시스템 분석

### 기존 대화 저장 시스템
- **대화 저장**: BigQuery `conversations` 테이블에 메시지별로 저장
- **사용자별 격리**: `user_id`로 사용자별 대화 분리
- **대화 세션**: `conversation_id`로 세션 단위 관리
- **메시지 타입**: `user`, `assistant`로 구분
- **메타데이터**: 시간, 쿼리 타입, SQL 등 저장

### 현재 LLM 호출 방식
- **단독 요청**: 각 메시지를 독립적으로 처리
- **컨텍스트 부재**: 이전 대화 내용을 참조하지 않음
- **실시간 처리**: SSE 스트리밍으로 즉시 응답

## 구현 방안

### 0. 경량화된 데이터 모델 (필드 최소화)

본 기능 구현을 위해 테이블 스키마를 다음과 같이 정의합니다. 데이터베이스 성능 최적화(파티셔닝, 클러스터링)는 별도의 `Database Refactoring Plan.md` 문서에서 다룹니다.

#### `conversations` 테이블
*   **필수 컬럼**: `conversation_id`, `message_id`, `user_id`, `message`, `message_type`, `timestamp`, `generated_sql`, `query_id` (신규 추가). `query_id`는 대화와 쿼리 결과를 연결하는 핵심 컬럼입니다.

#### `query_results` 테이블 (필드 통합)
*   **경량화 방안**: 여러 메타데이터 컬럼을 두는 대신, **하나의 `result_payload` 컬럼에 모든 정보를 JSON 형태로 통합**하여 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `query_id` | `STRING` | 고유 ID (PK). `conversations` 테이블과 연결하는 핵심 키. |
| `result_payload` | `STRING` | 결과 데이터와 메타데이터를 포함하는 JSON 객체. |
| `creation_time`| `TIMESTAMP`| 데이터 생성 시간. 파티셔닝 및 데이터 수명 관리(TTL)에 사용. |

*   **`result_payload` JSON 구조 예시:**
    ```json
    {
      "status": "success",
      "metadata": {
        "row_count": 520,
        "data_size_kb": 128,
        "is_summary": true, // 데이터가 요약되었는지 여부
        "schema": [ // 데이터 스키마 정보
          {"name": "user_name", "type": "STRING"},
          {"name": "order_count", "type": "INTEGER"}
        ]
      },
      "data": [ /* 상위 10~20건의 요약 데이터 또는 전체 데이터 */ ]
    }
    ```

### 1. 대화 기록 조회 최적화

#### 1.1 conversation_service.py 확장
```python
def get_conversation_context(self, conversation_id: str, user_id: str, 
                           max_messages: int = 3) -> Dict[str, Any]:
    """
    LLM 컨텍스트용 대화 기록 조회 (최근 N개 메시지)
    
    Args:
        conversation_id: 대화 세션 ID
        user_id: 사용자 ID (권한 확인)
        max_messages: 최대 메시지 수 (기본 3개)
    
    Returns:
        LLM 호출용 대화 컨텍스트
    """
    try:
        dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
        query = f"""
        SELECT 
            message,
            message_type,
            timestamp,
            query_type,      -- SQL 생성 관련 메타데이터
            generated_sql,   -- SQL 생성 관련 메타데이터
            query_id         -- query_results 테이블과 연결하기 위한 ID
        FROM `{self.project_id}.{dataset_name}.conversations`
        WHERE conversation_id = @conversation_id 
          AND user_id = @user_id
        ORDER BY timestamp DESC
        LIMIT @max_messages
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("conversation_id", "STRING", conversation_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("max_messages", "INT64", max_messages)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        conversation_rows = list(query_job.result())
        
        # 2. SQL 실행 결과가 있는 경우, query_results 테이블에서 데이터 일괄 조회
        query_ids = [row.query_id for row in conversation_rows if row.query_id]
        query_results_map = {}
        if query_ids:
            # 가정: query_results 테이블에는 query_id와 결과(예: result_data) 컬럼이 있음
            # result_data는 JSON 형식의 문자열로 저장되어 있다고 가정
            # 경량화된 스키마에 맞춰 result_payload 컬럼을 조회
            payload_query = f"""
            SELECT query_id, result_payload
            FROM `{self.project_id}.{dataset_name}.query_results`
            WHERE query_id IN UNNEST(@query_ids)
            """
            payload_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("query_ids", "STRING", query_ids)
                ]
            )
            payload_job = self.client.query(payload_query, job_config=payload_job_config)
            for payload_row in payload_job.result():
                try:
                    # result_payload를 파싱하여 필요한 데이터(요약본)를 컨텍스트에 추가
                    payload = json.loads(payload_row.result_payload)
                    if payload.get("status") == "success":
                        # LLM 컨텍스트에는 실제 데이터(요약본)와 스키마 정보만 포함시켜 경량화
                        query_results_map[payload_row.query_id] = {
                            "data": payload.get("data", []),
                            "schema": payload.get("metadata", {}).get("schema", [])
                        }
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Query result payload parsing failed for query_id: {payload_row.query_id}")
                    query_results_map[payload_row.query_id] = None

        # 3. 대화 기록과 SQL 결과를 결합하여 최종 컨텍스트 생성
        messages = []
        for row in reversed(conversation_rows): # 시간순으로 다시 정렬 (최신이 마지막)
            metadata = {
                "query_type": row.query_type,
                "generated_sql": row.generated_sql
            }
            # 조회된 쿼리 결과를 메타데이터에 추가
            if row.query_id and query_results_map.get(row.query_id):
                metadata["query_results"] = query_results_map.get(row.query_id)

            messages.append({
                "role": "user" if row.message_type == "user" else "assistant",
                "content": row.message,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "metadata": metadata
            })
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": messages,
            "context_length": len(messages)
        }
        
    except Exception as e:
        logger.error(f"대화 컨텍스트 조회 오류: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "messages": []
        }
```

#### 1.2 컨텍스트 크기 관리
```python
def optimize_context_size(self, messages: List[Dict], max_tokens: int = 2000) -> List[Dict]:
    """
    토큰 제한에 맞춰 컨텍스트 최적화
    
    Args:
        messages: 원본 메시지 리스트
        max_tokens: 최대 토큰 수 (한글 기준 최적화: 기본 2000토큰)
    
    Returns:
        최적화된 메시지 리스트
    """
    # 한글 토큰 추정 최적화 (1토큰 ≈ 2-3글자, 안전하게 2.5 적용)
    total_chars = sum(len(msg['content']) for msg in messages)
    estimated_tokens = total_chars // 2.5  # 한글 특성 고려
    
    if estimated_tokens <= max_tokens:
        return messages
    
    # 최신 메시지부터 유지하면서 크기 조절
    optimized_messages = []
    current_chars = 0
    
    for message in reversed(messages):
        msg_chars = len(message['content'])
        if (current_chars + msg_chars) // 2.5 > max_tokens:
            break
        optimized_messages.insert(0, message)
        current_chars += msg_chars
    
    return optimized_messages
```

### 2. LLM 클라이언트 확장

#### 2.1 llm_client.py 컨텍스트 지원 추가

**컨텍스트 기반 분류 분기 확장:**
- **follow_up_query**: 이전 쿼리 결과에 대한 추가 질문
- **refinement_request**: 이전 쿼리 수정/개선 요청
- **comparison_analysis**: 이전 결과와의 비교 분석
- **clarification_request**: 이전 응답에 대한 명확화 요청

**실제 구현:**
- `backend/utils/prompts/classification.json` - 하나의 파일에 모든 분류 템플릿 통합
  - `system_prompt`: 기본 분류 (9개 카테고리)
  - `user_prompt`: 기본 사용자 입력
  - `system_prompt_with_context`: 컨텍스트 고려 분류
  - `user_prompt_with_context`: 컨텍스트 포함 사용자 입력

#### 2.2 모든 프롬프트 카테고리에 컨텍스트 지원 확장

**확장 대상 프롬프트:**

##### A. SQL Generation 컨텍스트 지원
- **이전 SQL 패턴 참조**: 테이블명, 컬럼명, WHERE 조건 재사용
- **점진적 쿼리 개선**: "그 중에서 활성 사용자만" → 기존 쿼리에 WHERE 추가
- **테이블 연관성 학습**: 자주 사용되는 테이블 조합 기억

```json
// sql_generation.json 확장
{
  "system_prompt_with_context": {
    "content": "이전 SQL 패턴을 참고하여 효율적인 BigQuery SQL을 생성하세요.\n\n이전 사용된 테이블: {frequently_used_tables}\n최근 SQL 패턴:\n{previous_sqls}\n\n컨텍스트를 고려하여 일관성 있는 SQL을 생성해주세요.",
    "variables": ["frequently_used_tables", "previous_sqls"]
  },
  "user_prompt_with_context": {
    "content": "이전 대화:\n{conversation_context}\n\n현재 질문: {question}\n\n이전 SQL을 참고하여 연관성 있는 쿼리를 생성해주세요.",
    "variables": ["conversation_context", "question"]
  }
}
```

##### B. Data Analysis 컨텍스트 지원
- **연속 분석**: 이전 분석 결과를 바탕으로 심화 분석
- **비교 분석**: "이전 결과와 비교해서" 요청 처리
- **트렌드 추적**: 시계열 데이터의 연속적 분석

```json
// data_analysis.json 확장
{
  "user_prompt_with_context": {
    "content": "당신은 데이터 분석가입니다. 아래의 이전 대화 내용을 참고하여, '분석할 데이터'를 가지고 사용자의 '현재 질문'에 답변해주세요.\n\n### 이전 대화 내용:\n{conversation_context}\n\n### 분석할 데이터:\n```json\n{data_to_analyze}\n```\n\n### 사용자의 현재 질문:\n{question}\n\n주어진 데이터와 대화 기록을 바탕으로 명확하고 통찰력 있는 분석을 제공해주세요.",
    "variables": ["conversation_context", "data_to_analyze", "question"]
  }
}
```


##### D. 통합된 컨텍스트 처리 아키텍처

**🔄 중복 제거 및 통합 설계:**

모든 `_with_context()` 함수들의 공통 패턴을 통합하여 중복을 제거합니다.

```python
# llm_client.py 통합 아키텍처
class AnthropicLLMClient(BaseLLMClient):
    
    def _execute_with_context(self, 
                            category: str,
                            input_data: Dict[str, Any],
                            conversation_context: List[Dict] = None,
                            context_processor: callable = None) -> dict:
        """
        모든 컨텍스트 기반 LLM 호출의 통합 메서드
        
        Args:
            category: 프롬프트 카테고리 ('classification', 'sql_generation' 등)
            input_data: 입력 데이터 (user_input, question, data 등)
            conversation_context: 이전 대화 기록
            context_processor: 카테고리별 컨텍스트 처리 함수
            
        Returns:
            LLM 응답 결과
        """
    
    # 각 기능별 래퍼 메서드들
    def classify_input(self, user_input: str, conversation_context: List[Dict] = None) -> dict:
        """통합 메서드를 활용한 분류"""
        return self._execute_with_context(
            category='classification',
            input_data={'user_input': user_input},
            conversation_context=conversation_context,
            context_processor=self._process_classification_context
        )
    
    def generate_sql(self, question: str, project_id: str, 
                   conversation_context: List[Dict] = None) -> dict:
        """통합 메서드를 활용한 SQL 생성"""
        return self._execute_with_context(
            category='sql_generation', 
            input_data={'question': question, 'project_id': project_id},
            conversation_context=conversation_context,
            context_processor=self._process_sql_context
        )
    
    def analyze_data(self, question: str, data: list,
                   conversation_context: List[Dict] = None) -> dict:
        """통합 메서드를 활용한 데이터 분석"""
        return self._execute_with_context(
            category='data_analysis',
            input_data={'question': question, 'data': data},
            conversation_context=conversation_context, 
            context_processor=self._process_analysis_context
        )
    
    # 카테고리별 컨텍스트 처리기들
    def _process_classification_context(self, context: List[Dict]) -> Dict[str, Any]:
        """분류용 컨텍스트 처리"""
        return {'formatted_context': self._format_conversation_context(context)}
    
    def _process_sql_context(self, context: List[Dict]) -> Dict[str, Any]:
        """SQL 생성용 컨텍스트 처리"""
        return {
            'formatted_context': self._format_conversation_context(context),
            'previous_sqls': self._extract_sql_patterns(context),
            'frequently_used_tables': self._extract_table_usage(context)
        }
    
    def _process_analysis_context(self, context: List[Dict]) -> Dict[str, Any]:
        """분석용 컨텍스트 처리"""
        return {
            'formatted_context': self._format_conversation_context(context),
            'previous_analysis': self._extract_previous_analysis(context)
        }
```

**🎯 통합의 장점:**

1. **중복 제거**: 공통 로직을 `_execute_with_context()`로 통합
2. **일관성**: 모든 기능이 동일한 컨텍스트 처리 방식 사용
3. **확장성**: 새로운 기능 추가 시 context_processor만 구현
4. **유지보수**: 컨텍스트 로직 변경 시 한 곳만 수정
5. **테스트**: 통합 메서드만 테스트하면 모든 기능 검증
```python
class AnthropicLLMClient(BaseLLMClient):
    def classify_input_with_context(self, user_input: str, 
                                  conversation_context: List[Dict] = None) -> dict:
        """
        대화 컨텍스트를 고려한 입력 분류
        
        Args:
            user_input: 현재 사용자 입력
            conversation_context: 이전 대화 기록
        
        Returns:
            분류 결과
        """
        try:
            system_prompt = prompt_manager.get_prompt(
                category='classification',
                template_name='system_prompt_with_context',
                fallback_prompt=self._get_fallback_classification_prompt()
            )
            
            # 컨텍스트가 있는 경우 프롬프트에 포함
            if conversation_context:
                context_text = self._format_conversation_context(conversation_context)
                user_prompt = prompt_manager.get_prompt(
                    category='classification',
                    template_name='user_prompt_with_context',
                    user_input=user_input,
                    conversation_context=context_text,
                    fallback_prompt=f"이전 대화:\n{context_text}\n\n현재 입력: {user_input}\n\n추가 분류 고려사항:\n- follow_up_query: 이전 쿼리 결과에 대한 후속 질문\n- refinement_request: 이전 쿼리 수정 요청\n- comparison_analysis: 비교 분석 요청\n- clarification_request: 명확화 요청"
                )
            else:
                user_prompt = prompt_manager.get_prompt(
                    category='classification',
                    template_name='user_prompt',
                    user_input=user_input,
                    fallback_prompt=f"분류할 입력: {user_input}"
                )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            # 응답 파싱 로직...
            
        except Exception as e:
            logger.error(f"컨텍스트 분류 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _format_conversation_context(self, context: List[Dict]) -> str:
        """대화 컨텍스트를 LLM 프롬프트용 텍스트로 변환"""
        if not context:
            return ""
        
        formatted_lines = []
        for msg in context[-5:]:  # 최근 5개 메시지만 사용
            role = "사용자" if msg['role'] == "user" else "AI"
            timestamp = msg.get('timestamp', '')[:19] if msg.get('timestamp') else ''
            formatted_lines.append(f"[{timestamp}] {role}: {msg['content'][:200]}...")
        
        return "\n".join(formatted_lines)
```

### 4. 구현 우선순위

#### Phase 1: 기본 컨텍스트 지원 ✅ **완료**
1. ✅ `conversation_service.py`에 `get_conversation_context()` 메서드 추가
2. ✅ `llm_client.py`에 컨텍스트 지원 메서드 추가 (`classify_input_with_context`)
3. ✅ 기본 프롬프트 템플릿 확장 (`classification.json`)
4. ✅ user_id 기반 대화 관리 시스템 완료 (conversation_id 제거)
5. ✅ 컨텍스트 기반 분류 시스템 동작 확인

#### Phase 2: 통합된 컨텍스트 아키텍처 구현
1. **통합 컨텍스트 처리 시스템**
   - `_execute_with_context()` 핵심 메서드 구현
   - 모든 `_with_context()` 함수 중복 제거
   - 카테고리별 context_processor 패턴 적용

2. **프롬프트 템플릿 확장**  
   - `sql_generation.json`, `data_analysis.json`에 컨텍스트 템플릿 추가
   - 통일된 템플릿 네이밍: `system_prompt_with_context`, `user_prompt_with_context`

3. **기존 메서드 리팩토링**
   - `classify_input()`, `generate_sql()`, `analyze_data()` 등을 통합 아키텍처로 전환
   - 하위 호환성 유지하면서 내부 구현만 변경

4. **채팅 라우트 통합**
   - `chat_routes.py`에서 리팩토링된 메서드들 사용
   - 확장된 분류 카테고리 처리 로직 구현

### 5. 핵심 테스트 시나리오

#### 5.1 기본 컨텍스트 동작 테스트
1. **후속 질문**: "사용자 데이터 보여줘" → "그 중에서 활성 사용자만"
2. **분류 정확도**: 컨텍스트 유무에 따른 분류 카테고리 비교
3. **SQL 개선**: 이전 SQL 패턴을 활용한 쿼리 개선 확인

#### 5.2 통합 아키텍처 검증
1. **중복 제거**: `_execute_with_context()` 통합 동작 확인
2. **하위 호환성**: 기존 메서드 호출 시 정상 작동 확인

### 6. 구현 단계별 체크리스트

#### Phase 2 핵심 작업:
- [ ] `_execute_with_context()` 통합 메서드 구현
- [ ] `sql_generation.json`, `data_analysis.json` 컨텍스트 템플릿 추가
- [ ] 기존 메서드를 통합 아키텍처로 리팩토링
- [ ] 기본 테스트 시나리오 검증