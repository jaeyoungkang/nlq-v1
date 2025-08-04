"""
Anthropic Claude API 유틸리티 클래스
자연어 질문을 BigQuery SQL로 변환하는 기능을 담당
"""

import logging
import re
from typing import Dict, List, Optional
import anthropic

logger = logging.getLogger(__name__)

class AnthropicClient:
    """Anthropic Claude API 클라이언트 래퍼"""
    
    def __init__(self, api_key: str):
        """
        Anthropic 클라이언트 초기화
        
        Args:
            api_key: Anthropic API 키
        """
        self.api_key = api_key
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("Anthropic Claude 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"Anthropic 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None) -> dict:
        """
        자연어 질문을 BigQuery SQL로 변환
        
        Args:
            question: 사용자의 자연어 질문
            project_id: BigQuery 프로젝트 ID  
            dataset_ids: 사용할 데이터셋 ID 목록 (선택사항)
            
        Returns:
            SQL 생성 결과
        """
        try:
            # 시스템 프롬프트 생성
            system_prompt = self._create_sql_system_prompt(project_id, dataset_ids)
            
            # Claude API 호출
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": question}
                ]
            )
            
            # 응답에서 SQL 추출
            raw_sql = response.content[0].text.strip()
            cleaned_sql = self._clean_sql_response(raw_sql)
            
            logger.info(f"SQL 생성 완료: {cleaned_sql[:100]}...")
            
            return {
                "success": True,
                "sql": cleaned_sql,
                "raw_response": raw_sql
            }
            
        except Exception as e:
            logger.error(f"SQL 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "sql": None
            }
    
    def _create_sql_system_prompt(self, project_id: str, dataset_ids: List[str] = None) -> str:
        """BigQuery SQL 생성을 위한 시스템 프롬프트 생성"""
        
        # 기본 테이블 정보
        default_table = "`nlq-ex.test_dataset.events_20210131`"
        
        dataset_info = f"""
기본 테이블: {default_table}
- 이 테이블을 기본으로 사용하세요
- 사용자가 특정 테이블을 언급하지 않으면 이 테이블을 사용하세요
"""
        
        if dataset_ids:
            dataset_list = ", ".join([f"`{project_id}.{ds}`" for ds in dataset_ids])
            dataset_info += f"""
추가 사용 가능한 데이터셋: {dataset_list}
"""
        
        return f"""당신은 BigQuery SQL 전문가입니다. 사용자의 자연어 질문을 BigQuery SQL 쿼리로 변환해주세요.

## 프로젝트 정보
- 프로젝트 ID: {project_id}
{dataset_info}

## 중요한 규칙

### 1. 테이블 참조
- 사용자가 특정 테이블을 언급하지 않으면 기본 테이블 {default_table}을 사용하세요
- 테이블 참조 시 반드시 백틱(`)을 사용하세요: `project.dataset.table`
- SQL 쿼리만 반환하고, 다른 설명은 포함하지 마세요
- 쿼리는 반드시 세미콜론(;)으로 끝나야 합니다

### 2. 성능 최적화
- 대용량 테이블의 경우 LIMIT 절을 사용하여 결과를 제한하세요 (기본 100개)
- 필요한 컬럼만 SELECT 하여 스캔량을 최소화하세요
- WHERE 절을 사용하여 데이터를 적절히 필터링하세요

### 3. 데이터 타입 처리
- TIMESTAMP 필드 처리 시 적절한 함수를 사용하세요: EXTRACT(), DATE(), etc.
- 문자열 처리 시 LIKE, REGEXP_CONTAINS 등을 활용하세요
- NULL 값 처리에 주의하세요 (IFNULL, COALESCE 활용)

### 4. 일반적인 분석 패턴
- **기본 통계**: COUNT, SUM, AVG, MIN, MAX
- **시계열 분석**: 날짜별, 월별, 연도별 트렌드
- **상위 N개**: ORDER BY + LIMIT를 활용
- **비율 계산**: 전체 대비 비율, 증감률 등

### 5. 안전한 쿼리 작성
- 항상 LIMIT을 사용하여 결과 크기를 제한하세요
- 집계 함수 사용 시 GROUP BY 절을 적절히 사용하세요
- 복잡한 JOIN은 필요한 경우에만 사용하세요

### 6. 예시 쿼리 패턴

**기본 조회** (기본 테이블 사용):
```sql
SELECT * FROM {default_table} LIMIT 10;
```

**집계 분석**:
```sql
SELECT 
    category,
    COUNT(*) as count,
    AVG(amount) as avg_amount
FROM {default_table}
GROUP BY category
ORDER BY count DESC
LIMIT 20;
```

**시계열 분석**:
```sql
SELECT 
    DATE(timestamp_field) as date,
    COUNT(*) as daily_count
FROM {default_table}
WHERE timestamp_field >= '2021-01-01'
GROUP BY DATE(timestamp_field)
ORDER BY date
LIMIT 100;
```

질문의 의도를 정확히 파악하여 효율적이고 안전한 BigQuery SQL을 생성해주세요.
결과는 SQL 쿼리만 반환하고, 추가 설명은 포함하지 마세요."""

    def _clean_sql_response(self, raw_response: str) -> str:
        """Claude 응답에서 SQL 쿼리만 추출하고 정리"""
        
        # 마크다운 코드 블록 제거
        if '```sql' in raw_response:
            sql_match = re.search(r'```sql\n(.*?)\n```', raw_response, re.DOTALL)
            if sql_match:
                raw_response = sql_match.group(1)
        elif '```' in raw_response:
            # 일반 코드 블록 제거
            code_blocks = re.findall(r'```(.*?)```', raw_response, re.DOTALL)
            if code_blocks:
                raw_response = code_blocks[0]
        
        # 앞뒤 공백 제거
        sql_query = raw_response.strip()
        
        # 주석 제거 (-- 로 시작하는 라인)
        lines = sql_query.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # SQL 주석 제거 (단, 실제 SQL 구문이 포함된 경우는 유지)
            if line.startswith('--') and not any(keyword in line.upper() for keyword in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT']):
                continue
            cleaned_lines.append(line)
        
        # 정리된 라인들을 다시 조합
        sql_query = '\n'.join(cleaned_lines)
        
        # 세미콜론이 없으면 추가
        if not sql_query.rstrip().endswith(';'):
            sql_query = sql_query.rstrip() + ';'
        
        return sql_query
    
    def explain_query(self, sql_query: str, question: str) -> dict:
        """
        생성된 SQL 쿼리에 대한 설명 생성
        
        Args:
            sql_query: 설명할 SQL 쿼리
            question: 원본 질문
            
        Returns:
            쿼리 설명 결과
        """
        try:
            explanation_prompt = f"""다음 SQL 쿼리가 어떤 작업을 수행하는지 간단하고 명확하게 설명해주세요.

원본 질문: {question}

SQL 쿼리:
```sql
{sql_query}
```

설명 시 다음 내용을 포함해주세요:
1. 쿼리가 수행하는 주요 작업
2. 사용된 테이블과 필드
3. 적용된 필터나 조건
4. 정렬 및 제한 사항
5. 예상되는 결과의 형태

간결하고 이해하기 쉽게 설명해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                messages=[
                    {"role": "user", "content": explanation_prompt}
                ]
            )
            
            explanation = response.content[0].text.strip()
            
            return {
                "success": True,
                "explanation": explanation
            }
            
        except Exception as e:
            logger.error(f"쿼리 설명 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "explanation": None
            }
    
    def suggest_improvements(self, sql_query: str) -> dict:
        """
        SQL 쿼리 개선 사항 제안
        
        Args:
            sql_query: 개선할 SQL 쿼리
            
        Returns:
            개선 제안 결과
        """
        try:
            improvement_prompt = f"""다음 BigQuery SQL 쿼리를 분석하고 성능 및 최적화 관점에서 개선 사항을 제안해주세요.

SQL 쿼리:
```sql
{sql_query}
```

다음 관점에서 분석해주세요:
1. 성능 최적화 (인덱스, 파티셔닝 활용 등)
2. 비용 절약 방안 (스캔량 최소화)
3. 가독성 개선
4. 잠재적 오류나 위험 요소
5. BigQuery 모범 사례 적용

각 제안사항에 대해 구체적인 이유와 개선된 쿼리 예시를 포함해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": improvement_prompt}
                ]
            )
            
            suggestions = response.content[0].text.strip()
            
            return {
                "success": True,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"개선 제안 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": None
            }
    
    def generate_sample_questions(self, project_id: str, dataset_ids: list = None) -> dict:
        """
        프로젝트와 데이터셋을 기반으로 샘플 질문들을 생성
        
        Args:
            project_id: BigQuery 프로젝트 ID
            dataset_ids: 데이터셋 ID 목록
            
        Returns:
            샘플 질문 목록
        """
        try:
            dataset_info = ""
            if dataset_ids:
                dataset_list = ", ".join(dataset_ids)
                dataset_info = f"사용 가능한 데이터셋: {dataset_list}"
            
            sample_prompt = f"""BigQuery 프로젝트에서 사용할 수 있는 유용한 질문 예시들을 생성해주세요.

프로젝트: {project_id}
{dataset_info}

다음과 같은 다양한 유형의 질문들을 포함해주세요:
1. 기본적인 데이터 조회 (예: "전체 데이터 개수는?")
2. 집계 및 통계 (예: "카테고리별 평균값은?")
3. 시계열 분석 (예: "월별 트렌드는?")
4. 상위/하위 분석 (예: "가장 많이 발생한 상위 10개는?")
5. 비교 분석 (예: "A와 B의 차이는?")

총 8-10개의 질문을 생성하고, 각 질문은 간단하고 명확하게 작성해주세요.
JSON 배열 형태로 반환해주세요: ["질문1", "질문2", ...]"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": sample_prompt}
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            # JSON 배열 형태의 응답에서 질문들 추출
            import json
            try:
                questions = json.loads(response_text)
                if isinstance(questions, list):
                    return {
                        "success": True,
                        "questions": questions
                    }
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트에서 질문 추출
                questions = self._extract_questions_from_text(response_text)
                return {
                    "success": True,
                    "questions": questions
                }
            
            return {
                "success": False,
                "error": "응답 형식을 파싱할 수 없습니다",
                "questions": []
            }
            
        except Exception as e:
            logger.error(f"샘플 질문 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "questions": []
            }
    
    def classify_user_input(self, user_input: str) -> dict:
        """
        사용자 입력을 카테고리별로 분류
        
        Args:
            user_input: 사용자 입력 텍스트
            
        Returns:
            분류 결과 딕셔너리
        """
        try:
            classification_prompt = """사용자의 입력을 다음 4개 카테고리 중 하나로 분류해주세요:

1. **query_request** - BigQuery 데이터 조회 요청
   - 예: "상위 이벤트 5개는?", "테이블 스키마", "전체 데이터 개수는?", "현재 연결된 테이블은?"
   
2. **data_analysis** - 이미 조회된 데이터에 대한 분석 요청
   - 예: "데이터 해설 해줘", "추가로 어떤 데이터를 보면 좋을까?", "이 결과의 의미는?"
   
3. **guide_request** - 사용법이나 다음 단계에 대한 안내 요청
   - 예: "어떤 데이터를 보면 좋을까?", "이제 뭐해야하지?", "뭘 할 수 있나요?"
   
4. **out_of_scope** - 기능 범위 외의 요청
   - 예: "오늘 날씨는?", "안녕하세요", "다른 주제 질문들"

다음 JSON 형식으로만 응답해주세요:
{
  "category": "분류된_카테고리",
  "confidence": 0.95,
  "reasoning": "분류 이유 간단 설명"
}"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                system=classification_prompt,
                messages=[
                    {"role": "user", "content": f"분류할 입력: {user_input}"}
                ]
            )
            
            response_text = response.content[0].text.strip()
            
            # JSON 파싱 시도
            import json
            try:
                classification = json.loads(response_text)
                
                # 필수 필드 검증
                if "category" in classification and "confidence" in classification:
                    return {
                        "success": True,
                        "classification": classification
                    }
                else:
                    raise ValueError("필수 필드 누락")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"분류 응답 파싱 실패: {e}")
                # 기본값 반환
                return {
                    "success": True,
                    "classification": {
                        "category": "query_request",
                        "confidence": 0.5,
                        "reasoning": "분류 파싱 실패로 기본값 사용"
                    }
                }
            
        except Exception as e:
            logger.error(f"사용자 입력 분류 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "classification": {
                    "category": "query_request",
                    "confidence": 0.3,
                    "reasoning": "분류 실패로 기본값 사용"
                }
            }
        """텍스트에서 질문들을 추출하는 헬퍼 함수"""
        questions = []
        
        # 다양한 패턴으로 질문 추출 시도
        patterns = [
            r'"([^"]+\?)"',  # 따옴표로 둘러싸인 질문
            r'(\d+\.\s+[^?\n]+\?)',  # 번호가 붙은 질문
            r'([A-Z][^?\n]*\?)',  # 대문자로 시작하는 질문
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_question = match.strip()
                if clean_question and len(clean_question) > 10:
                    questions.append(clean_question)
        
        # 중복 제거 및 최대 10개로 제한
        unique_questions = list(dict.fromkeys(questions))[:10]
        
        # 기본 질문들이 없을 경우 기본값 제공
        if not unique_questions:
            unique_questions = [
                "전체 데이터의 행 수는 얼마나 되나요?",
                "가장 최근 데이터는 언제인가요?",
                "각 카테고리별 데이터 수는?",
                "월별 데이터 추이는 어떻게 되나요?",
                "상위 10개 항목은 무엇인가요?"
            ]
        
        return unique_questions

    def generate_data_analysis(self, user_question: str, previous_data: list = None, previous_sql: str = None) -> dict:
        """
        조회된 데이터에 대한 분석 생성
        
        Args:
            user_question: 사용자의 분석 요청 질문
            previous_data: 이전에 조회된 데이터
            previous_sql: 이전에 실행된 SQL
            
        Returns:
            데이터 분석 결과
        """
        try:
            import json
            data_context = ""
            if previous_data and previous_sql:
                # 데이터 요약
                data_sample = previous_data[:5] if len(previous_data) > 5 else previous_data
                data_context = f"""
최근 실행된 SQL:
```sql
{previous_sql}
```

조회 결과 (샘플):
```json
{json.dumps(data_sample, indent=2, ensure_ascii=False, default=str)}
```

총 {len(previous_data)}개 행이 조회되었습니다.
"""
            
            analysis_prompt = f"""다음 BigQuery 데이터를 간결하게 분석해주세요.

{data_context}

사용자 질문: {user_question}

다음 관점에서 간단히 분석해주세요:
1. 주요 데이터 특징 (2-3개)
2. 핵심 인사이트 (1-2개)
3. 추가 분석 제안 (1개)

불필요한 설명은 제외하고 핵심만 간결하게 답변해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                messages=[
                    {"role": "user", "content": analysis_prompt}
                ]
            )
            
            analysis = response.content[0].text.strip()
            
            return {
                "success": True,
                "analysis": analysis,
                "type": "data_analysis"
            }
            
        except Exception as e:
            logger.error(f"데이터 분석 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }

    def generate_guide_response(self, user_question: str, context: str = "") -> dict:
        """
        가이드 응답 생성
        
        Args:
            user_question: 사용자의 가이드 요청
            context: 현재 상황 컨텍스트
            
        Returns:
            가이드 응답 결과
        """
        try:
            guide_prompt = f"""당신은 BigQuery Assistant의 도우미입니다. 간결하고 명확하게 답변해주세요.

현재 상황: {context}
사용자 질문: {user_question}

다음을 간단히 답변해주세요:
1. 사용 가능한 주요 기능 (3개)
2. 추천하는 다음 단계 (1-2개)
3. 구체적인 질문 예시 (3개)

불필요한 설명은 제외하고 핵심만 전달해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": guide_prompt}
                ]
            )
            
            guide = response.content[0].text.strip()
            
            return {
                "success": True,
                "guide": guide,
                "type": "guide"
            }
            
        except Exception as e:
            logger.error(f"가이드 응답 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "guide": None
            }
    
    def generate_out_of_scope_response(self, user_question: str) -> dict:
        """
        기능 범위 외 요청에 대한 응답 생성
        
        Args:
            user_question: 사용자의 질문
            
        Returns:
            범위 외 응답 결과
        """
        try:
            scope_prompt = f"""사용자가 BigQuery Assistant의 기능 범위를 벗어난 질문을 했습니다.

사용자 질문: {user_question}

간결하게 답변해주세요:
1. 해당 질문은 도와드릴 수 없다는 안내
2. BigQuery Assistant 주요 기능 3가지
3. 사용 가능한 질문 예시 2개

짧고 명확하게 답변해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                messages=[
                    {"role": "user", "content": scope_prompt}
                ]
            )
            
            scope_response = response.content[0].text.strip()
            
            return {
                "success": True,
                "response": scope_response,
                "type": "out_of_scope"
            }
            
        except Exception as e:
            logger.error(f"범위 외 응답 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": None
            }