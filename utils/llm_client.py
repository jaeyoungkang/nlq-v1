"""
통합 LLM 클라이언트 - 모든 LLM 기능을 단일 인터페이스로 제공
리팩토링: anthropic_utils.py 기능을 완전히 통합하고 중복 제거
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import anthropic

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """LLM 클라이언트 추상 베이스 클래스"""
    
    @abstractmethod
    def classify_input(self, user_input: str) -> dict:
        """사용자 입력 분류"""
        pass
    
    @abstractmethod
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None) -> dict:
        """SQL 생성"""
        pass
    
    @abstractmethod
    def analyze_data(self, question: str, previous_data: list = None, previous_sql: str = None) -> dict:
        """데이터 분석"""
        pass
    
    @abstractmethod
    def generate_guide(self, question: str, context: str = "") -> dict:
        """가이드 생성"""
        pass
    
    @abstractmethod
    def generate_metadata_response(self, question: str, metadata: dict) -> dict:
        """메타데이터 응답 생성"""
        pass
    
    @abstractmethod
    def generate_out_of_scope(self, question: str) -> dict:
        """범위 외 응답 생성"""
        pass


class AnthropicLLMClient(BaseLLMClient):
    """Anthropic Claude LLM 클라이언트 - 통합 버전"""
    
    def __init__(self, api_key: str):
        """
        Anthropic 클라이언트 초기화
        
        Args:
            api_key: Anthropic API 키
        """
        self.api_key = api_key
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("✅ Anthropic LLM 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"❌ Anthropic 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def classify_input(self, user_input: str) -> dict:
        """
        사용자 입력을 카테고리별로 분류
        
        Args:
            user_input: 사용자 입력 텍스트
            
        Returns:
            분류 결과 딕셔너리
        """
        try:
            classification_prompt = """사용자 입력을 5개 카테고리로 분류하고 JSON으로 응답:

1. **query_request** - BigQuery 데이터 조회 요청
   - 예: "상위 10개", "전체 개수", "통계", "테이블 스키마", "현재 테이블"
   
2. **metadata_request** - 테이블/스키마 정보 요청  
   - 예: "테이블 구조", "컬럼 정보", "스키마", "메타데이터"
   
3. **data_analysis** - 조회된 데이터 분석 요청
   - 예: "데이터 해석", "인사이트", "트렌드 분석", "패턴 발견"
   
4. **guide_request** - 사용법/안내 요청
   - 예: "사용법", "도움말", "뭘 할 수 있나요", "다음 단계"
   
5. **out_of_scope** - 기능 범위 외 요청
   - 예: "안녕", "날씨", "다른 주제"

JSON 형식으로만 응답: {"category": "분류", "confidence": 0.95, "reasoning": "이유"}"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                system=classification_prompt,
                messages=[{"role": "user", "content": f"분류할 입력: {user_input}"}]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                classification = json.loads(response_text)
                
                # 필수 필드 검증
                if all(key in classification for key in ["category", "confidence"]):
                    logger.info(f"🎯 입력 분류: {classification['category']} (신뢰도: {classification['confidence']})")
                    return {"success": True, "classification": classification}
                else:
                    raise ValueError("필수 필드 누락")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ 분류 응답 파싱 실패: {e}")
                return {
                    "success": True,
                    "classification": {
                        "category": "query_request",
                        "confidence": 0.5,
                        "reasoning": "분류 파싱 실패로 기본값 사용"
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ 사용자 입력 분류 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "classification": {
                    "category": "query_request", 
                    "confidence": 0.3,
                    "reasoning": "분류 실패로 기본값 사용"
                }
            }
    
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None) -> dict:
        """
        자연어 질문을 BigQuery SQL로 변환 (통합된 버전)
        
        Args:
            question: 사용자의 자연어 질문
            project_id: BigQuery 프로젝트 ID  
            dataset_ids: 사용할 데이터셋 ID 목록 (선택사항)
            
        Returns:
            SQL 생성 결과
        """
        try:
            # 통합된 시스템 프롬프트 생성
            system_prompt = self._create_sql_system_prompt(project_id, dataset_ids)
            
            # Claude API 호출
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": question}]
            )
            
            # 응답에서 SQL 추출 및 정리
            raw_sql = response.content[0].text.strip()
            cleaned_sql = self._clean_sql_response(raw_sql)
            
            logger.info(f"🔧 SQL 생성 완료: {cleaned_sql[:100]}...")
            
            return {
                "success": True,
                "sql": cleaned_sql,
                "raw_response": raw_sql
            }
            
        except Exception as e:
            logger.error(f"❌ SQL 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "sql": None
            }
    
    def generate_metadata_response(self, question: str, metadata: dict) -> dict:
        """
        메타데이터 기반 응답 생성
        
        Args:
            question: 사용자 질문
            metadata: BigQuery 테이블 메타데이터
            
        Returns:
            메타데이터 응답 결과
        """
        try:
            table_info = metadata.get('table_info', {})
            schema = metadata.get('schema', [])
            
            # 스키마 정보를 텍스트로 변환
            schema_text = ""
            if schema:
                schema_text = "\n".join([
                    f"- {field['name']} ({field['type']}): {field.get('description', '설명 없음')}"
                    for field in schema[:10]  # 상위 10개만
                ])
            
            prompt = f"""BigQuery 테이블 메타데이터를 사용자 친화적으로 설명해주세요.

테이블 정보:
- 테이블 ID: {table_info.get('table_id', 'nlq-ex.test_dataset.events_20210131')}
- 행 수: {table_info.get('num_rows', 'N/A'):,}
- 크기: {table_info.get('size_mb', 'N/A')} MB  
- 생성일: {table_info.get('created', 'N/A')}

스키마 (주요 컬럼):
{schema_text}

사용자 질문: {question}

간결하고 이해하기 쉽게 답변해주세요. 필요시 활용 예시도 포함하세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            logger.info(f"📋 메타데이터 응답 생성 완료")
            
            return {
                "success": True,
                "response": response_text
            }
            
        except Exception as e:
            logger.error(f"❌ 메타데이터 응답 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def analyze_data(self, question: str, previous_data: list = None, previous_sql: str = None) -> dict:
        """
        조회된 데이터에 대한 분석 생성
        
        Args:
            question: 사용자의 분석 요청 질문
            previous_data: 이전에 조회된 데이터
            previous_sql: 이전에 실행된 SQL
            
        Returns:
            데이터 분석 결과
        """
        try:
            data_context = ""
            if previous_data and previous_sql:
                # 데이터 요약 (최대 5개 샘플)
                data_sample = previous_data[:5] if len(previous_data) > 5 else previous_data
                data_context = f"""
최근 실행된 SQL:
```sql
{previous_sql}
```

조회 결과 샘플:
```json
{json.dumps(data_sample, indent=2, ensure_ascii=False, default=str)}
```

총 {len(previous_data)}개 행이 조회되었습니다.
"""
            
            analysis_prompt = f"""다음 BigQuery 데이터를 분석해주세요.

{data_context}

사용자 질문: {question}

다음 관점에서 간결하게 분석해주세요:
1. **주요 데이터 특징** (2-3개)
2. **핵심 인사이트** (1-2개)  
3. **추가 분석 제안** (1-2개)

비즈니스적 관점에서 실용적으로 답변해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            analysis = response.content[0].text.strip()
            logger.info(f"🔍 데이터 분석 완료")
            
            return {
                "success": True,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"❌ 데이터 분석 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }

    def generate_guide(self, question: str, context: str = "") -> dict:
        """
        가이드 응답 생성
        
        Args:
            question: 사용자의 가이드 요청
            context: 현재 상황 컨텍스트
            
        Returns:
            가이드 응답 결과
        """
        try:
            guide_prompt = f"""BigQuery Assistant 사용 가이드를 제공해주세요.

현재 상황: {context}
사용자 질문: {question}

다음을 간단명료하게 답변해주세요:
1. **주요 기능** (3개)
2. **추천 다음 단계** (1-2개)
3. **구체적인 질문 예시** (3개)

사용자가 바로 시도해볼 수 있도록 실용적으로 안내해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": guide_prompt}]
            )
            
            guide = response.content[0].text.strip()
            logger.info(f"💡 가이드 응답 생성 완료")
            
            return {
                "success": True,
                "guide": guide
            }
            
        except Exception as e:
            logger.error(f"❌ 가이드 응답 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "guide": None
            }
    
    def generate_out_of_scope(self, question: str) -> dict:
        """
        기능 범위 외 요청에 대한 응답 생성
        
        Args:
            question: 사용자의 질문
            
        Returns:
            범위 외 응답 결과
        """
        try:
            scope_prompt = f"""사용자가 BigQuery Assistant의 기능 범위를 벗어난 질문을 했습니다.

사용자 질문: {question}

다음을 간결하게 답변해주세요:
1. **정중한 안내**: 해당 질문은 도와드릴 수 없다는 설명
2. **대신 가능한 기능** (3가지)
3. **시도해볼 수 있는 질문 예시** (2개)

친근하지만 명확하게 경계를 설정해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": scope_prompt}]
            )
            
            scope_response = response.content[0].text.strip()
            logger.info(f"🚫 범위 외 응답 생성 완료")
            
            return {
                "success": True,
                "response": scope_response
            }
            
        except Exception as e:
            logger.error(f"❌ 범위 외 응답 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": None
            }
    
    def _create_sql_system_prompt(self, project_id: str, dataset_ids: List[str] = None) -> str:
        """BigQuery SQL 생성을 위한 시스템 프롬프트 생성"""
        
        # 기본 테이블 정보
        default_table = "`nlq-ex.test_dataset.events_20210131`"
        
        dataset_info = f"""
기본 테이블: {default_table}
- 사용자가 특정 테이블을 언급하지 않으면 이 테이블을 기본으로 사용
- Events 데이터: user_id, event_timestamp, event_name, category, properties 컬럼 포함
"""
        
        if dataset_ids:
            dataset_list = ", ".join([f"`{project_id}.{ds}`" for ds in dataset_ids])
            dataset_info += f"""
추가 사용 가능한 데이터셋: {dataset_list}
"""
        
        return f"""당신은 BigQuery SQL 전문가입니다. 사용자의 자연어 질문을 정확하고 효율적인 BigQuery SQL로 변환해주세요.

## 프로젝트 정보
- 프로젝트 ID: {project_id}
{dataset_info}

## 핵심 규칙

### 1. 테이블 참조 & 출력
- 기본 테이블: {default_table} 사용
- 백틱(`) 필수 사용: `project.dataset.table`  
- **SQL 쿼리만 반환**, 설명/주석 제외
- 반드시 세미콜론(;)으로 종료

### 2. 성능 최적화
- LIMIT 기본 100개 (명시적 요청 시 조정)
- 필요한 컬럼만 SELECT
- WHERE 절로 적절한 필터링
- ORDER BY + LIMIT 조합 활용

### 3. 데이터 타입 처리
- TIMESTAMP: EXTRACT(), DATE(), FORMAT_TIMESTAMP() 활용
- 문자열: LIKE, REGEXP_CONTAINS, LOWER() 활용  
- NULL 처리: IFNULL, COALESCE 사용

### 4. 일반적인 패턴
**기본 조회**: `SELECT * FROM {default_table} LIMIT 10;`
**집계 분석**: 
```sql
SELECT category, COUNT(*) as count 
FROM {default_table} 
GROUP BY category 
ORDER BY count DESC LIMIT 20;
```
**시계열**: 
```sql
SELECT DATE(event_timestamp) as date, COUNT(*) as daily_count
FROM {default_table}
GROUP BY DATE(event_timestamp) 
ORDER BY date LIMIT 100;
```

효율적이고 안전한 BigQuery SQL만 생성해주세요."""

    def _clean_sql_response(self, raw_response: str) -> str:
        """Claude 응답에서 SQL 쿼리만 추출하고 정리"""
        
        # 마크다운 코드 블록 제거
        if '```sql' in raw_response:
            sql_match = re.search(r'```sql\s*\n(.*?)\n```', raw_response, re.DOTALL)
            if sql_match:
                raw_response = sql_match.group(1)
        elif '```' in raw_response:
            code_match = re.search(r'```(.*?)```', raw_response, re.DOTALL)
            if code_match:
                raw_response = code_match.group(1)
        
        # 정리 과정
        sql_query = raw_response.strip()
        
        # 주석 제거 (SQL 키워드가 포함되지 않은 라인만)
        lines = sql_query.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 주석이지만 SQL 구문이 포함된 경우는 유지
            if line.startswith('--') and not any(
                keyword in line.upper() 
                for keyword in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT']
            ):
                continue
            cleaned_lines.append(line)
        
        # 재조합
        sql_query = '\n'.join(cleaned_lines)
        
        # 세미콜론 추가
        if not sql_query.rstrip().endswith(';'):
            sql_query = sql_query.rstrip() + ';'
        
        return sql_query

    # === 추가 유틸리티 메서드 (기존 anthropic_utils.py에서 이전) ===
    
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
            explanation_prompt = f"""다음 SQL 쿼리를 간단명료하게 설명해주세요.

원본 질문: {question}

SQL 쿼리:
```sql
{sql_query}
```

다음 내용을 포함하여 설명해주세요:
1. 쿼리의 주요 목적
2. 사용된 테이블과 주요 필드
3. 적용된 조건이나 필터
4. 예상되는 결과 형태

기술적이지 않게 비즈니스 관점에서 설명해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                messages=[{"role": "user", "content": explanation_prompt}]
            )
            
            explanation = response.content[0].text.strip()
            logger.info(f"📝 쿼리 설명 생성 완료")
            
            return {
                "success": True,
                "explanation": explanation
            }
            
        except Exception as e:
            logger.error(f"❌ 쿼리 설명 생성 중 오류: {str(e)}")
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
            improvement_prompt = f"""다음 BigQuery SQL의 개선 사항을 제안해주세요.

SQL 쿼리:
```sql
{sql_query}
```

다음 관점에서 분석하고 개선안을 제시해주세요:
1. **성능 최적화** (스캔량, 실행시간)
2. **비용 절약** (BigQuery 비용 관점)
3. **가독성 개선** (코드 구조)
4. **안전성** (잠재적 위험요소)

구체적인 개선된 쿼리 예시와 함께 설명해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": improvement_prompt}]
            )
            
            suggestions = response.content[0].text.strip()
            logger.info(f"💡 쿼리 개선 제안 생성 완료")
            
            return {
                "success": True,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"❌ 개선 제안 생성 중 오류: {str(e)}")
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

다음 유형의 질문들을 포함해주세요:
1. **기본 조회** (전체 데이터, 상위 N개)
2. **집계 통계** (카테고리별 분석, 평균값)
3. **시계열 분석** (월별, 시간대별 트렌드)
4. **순위 분석** (상위/하위 순위)
5. **비교 분석** (그룹간 비교)

총 8-10개의 실용적인 질문을 JSON 배열로 반환: ["질문1", "질문2", ...]"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": sample_prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # JSON 배열 파싱 시도
            try:
                questions = json.loads(response_text)
                if isinstance(questions, list):
                    logger.info(f"📝 샘플 질문 {len(questions)}개 생성 완료")
                    return {
                        "success": True,
                        "questions": questions
                    }
            except json.JSONDecodeError:
                # 파싱 실패시 텍스트에서 추출
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
            logger.error(f"❌ 샘플 질문 생성 중 오류: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "questions": []
            }
    
    def _extract_questions_from_text(self, text: str) -> List[str]:
        """텍스트에서 질문들을 추출하는 헬퍼 함수"""
        questions = []
        
        # 다양한 패턴으로 질문 추출
        patterns = [
            r'"([^"]+\?)"',  # 따옴표로 둘러싸인 질문
            r'(\d+\.\s+[^?\n]+\?)',  # 번호가 붙은 질문
            r'([A-Z가-힣][^?\n]*\?)',  # 대문자/한글로 시작하는 질문
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


class LLMClientFactory:
    """LLM 클라이언트 팩토리 - 확장 가능한 구조"""
    
    @staticmethod
    def create_client(provider: str, config: dict) -> BaseLLMClient:
        """
        LLM 클라이언트 생성
        
        Args:
            provider: LLM 제공업체 ('anthropic', 'openai' 등)
            config: 설정 딕셔너리 (api_key 등)
            
        Returns:
            BaseLLMClient 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 프로바이더인 경우
        """
        providers = {
            "anthropic": AnthropicLLMClient,
            # 향후 추가 가능: "openai": OpenAILLMClient
        }
        
        if provider not in providers:
            supported = ", ".join(providers.keys())
            raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider}. 지원 목록: {supported}")
        
        try:
            client_class = providers[provider]
            client = client_class(config["api_key"])
            logger.info(f"✅ {provider} LLM 클라이언트 생성 완료")
            return client
        except Exception as e:
            logger.error(f"❌ {provider} LLM 클라이언트 생성 실패: {str(e)}")
            raise