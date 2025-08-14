# nlq-v1 백엔드 MetaSync 캐시 활용 구현계획

## 개요

MetaSync에서 생성된 스키마 정보와 Few-Shot 예시를 nlq-v1 백엔드의 SQL 생성 프로세스에 통합하여 쿼리 정확성과 품질을 향상시키는 계획입니다.

## 현재 상황

### ✅ 완료된 사항
- MetaSync 시스템 구축 및 배포 완료
- GCS에 캐시 데이터 생성 (23개 컬럼, 5개 예시)
- `metasync_cache_loader.py` 모듈 구현 완료
- 매일 자동 캐시 업데이트 설정 완료

### 📋 캐시 데이터 구조 확인
```json
{
  "generated_at": "2025-08-14T09:29:12.169051",
  "schema": {
    "table_id": "nlq-ex.test_dataset.events_20210131",
    "columns": [
      {"name": "event_name", "type": "STRING", "mode": "NULLABLE"},
      {"name": "event_timestamp", "type": "INTEGER", "mode": "NULLABLE"},
      // ... 총 23개 컬럼
    ]
  },
  "examples": [
    {
      "question": "총 이벤트 수는 얼마인가요?",
      "sql": "SELECT COUNT(*) as total_events FROM `nlq-ex.test_dataset.events_20210131`"
    }
    // ... 총 5개 예시
  ]
}
```

## 구현 계획

### 1단계: LLM Client 통합 (우선순위: 높음)

#### 1.1 llm_client.py 수정
**파일**: `backend/utils/llm_client.py`

**목표**: SQL 생성 시 MetaSync 캐시 데이터를 프롬프트에 자동 주입

**구현 내용**:
```python
# 기존 코드에 추가
from utils.metasync_cache_loader import get_metasync_cache_loader

class LLMClient:
    def __init__(self):
        # 기존 초기화 코드...
        self.cache_loader = get_metasync_cache_loader()
    
    def _execute_unified_prompting(self, category, user_input, conversation_context=None):
        # 기존 코드 유지하면서 캐시 데이터 추가
        
        # MetaSync 캐시 데이터 로드
        schema_info = self.cache_loader.get_schema_info()
        few_shot_examples = self.cache_loader.get_few_shot_examples()
        
        # 프롬프트에 동적 데이터 주입
        if category == 'query_request':
            # SQL 생성용 프롬프트에 스키마와 예시 추가
            enhanced_variables = {
                **variables,  # 기존 변수들
                'schema_columns': self._format_schema_for_prompt(schema_info.get('columns', [])),
                'few_shot_examples': self._format_examples_for_prompt(few_shot_examples),
                'table_id': schema_info.get('table_id', 'nlq-ex.test_dataset.events_20210131')
            }
            return self._call_llm_with_enhanced_prompt(enhanced_variables)
    
    def _format_schema_for_prompt(self, columns):
        """스키마 정보를 프롬프트에 적합한 형식으로 변환"""
        if not columns:
            return "스키마 정보를 로드할 수 없습니다."
        
        formatted_columns = []
        for col in columns:
            col_desc = f"- {col['name']} ({col['type']})"
            if col.get('description'):
                col_desc += f": {col['description']}"
            formatted_columns.append(col_desc)
        
        return "\n".join(formatted_columns)
    
    def _format_examples_for_prompt(self, examples):
        """Few-Shot 예시를 프롬프트에 적합한 형식으로 변환"""
        if not examples:
            return "예시를 로드할 수 없습니다."
        
        formatted_examples = []
        for i, example in enumerate(examples, 1):
            formatted_examples.append(f"""
예시 {i}:
질문: {example['question']}
SQL: {example['sql']}
""")
        
        return "\n".join(formatted_examples)
```

#### 1.2 프롬프트 템플릿 업데이트
**파일**: `backend/utils/prompts/sql_generation.json`

**목표**: 동적 스키마 정보와 Few-Shot 예시를 받을 수 있도록 템플릿 수정

**수정 내용**:
```json
{
  "system_prompt": {
    "content": "당신은 BigQuery SQL 생성 전문가입니다. 제공된 스키마 정보와 예시를 참고하여 정확한 SQL을 생성해주세요.\n\n**테이블 스키마**:\n{schema_columns}\n\n**참고 예시**:\n{few_shot_examples}\n\n현재 분석 대상 테이블: {table_id}",
    "variables": ["schema_columns", "few_shot_examples", "table_id"]
  }
}
```

### 2단계: 에러 처리 및 폴백 메커니즘 (우선순위: 높음)

#### 2.1 캐시 로드 실패 대응
```python
class LLMClient:
    def _get_cached_data_with_fallback(self):
        """캐시 데이터 로드 및 폴백 처리"""
        try:
            # MetaSync 캐시 사용 가능 여부 확인
            if not self.cache_loader.is_cache_available():
                logger.warning("MetaSync cache not available, using fallback")
                return self._get_fallback_data()
            
            schema_info = self.cache_loader.get_schema_info()
            examples = self.cache_loader.get_few_shot_examples()
            
            # 데이터 검증
            if not schema_info.get('columns') or not examples:
                logger.warning("MetaSync cache data incomplete, using fallback")
                return self._get_fallback_data()
            
            return {
                'schema_info': schema_info,
                'examples': examples,
                'source': 'metasync'
            }
            
        except Exception as e:
            logger.error(f"Failed to load MetaSync cache: {e}")
            return self._get_fallback_data()
    
    def _get_fallback_data(self):
        """캐시 로드 실패 시 기본 데이터 반환"""
        return {
            'schema_info': {
                'table_id': 'nlq-ex.test_dataset.events_20210131',
                'columns': []  # 빈 스키마로 처리
            },
            'examples': [],  # 빈 예시로 처리
            'source': 'fallback'
        }
```

### 구현
1. **LLM Client 통합**: `_execute_unified_prompting` 메서드 수정
2. **프롬프트 템플릿 업데이트**: 동적 변수 추가
3. **에러 처리**: 폴백 메커니즘 구현