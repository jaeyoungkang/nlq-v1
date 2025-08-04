"""
통합 LLM 클라이언트 - 다양한 LLM 프로바이더 지원
"""

import json
import logging
from abc import ABC, abstractmethod
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


class AnthropicLLMClient(BaseLLMClient):
    """Anthropic Claude LLM 클라이언트"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        logger.info("Anthropic LLM 클라이언트 초기화 완료")
    
    def classify_input(self, user_input: str) -> dict:
        try:
            prompt = """사용자 입력을 5개 카테고리로 분류하고 JSON으로 응답:
1. query_request - 데이터 조회 요청 (상위 N개, 개수, 통계 등)
2. metadata_request - 테이블/스키마 정보 요청 (테이블 구조, 컬럼 정보, 현재 테이블 등)
3. data_analysis - 조회된 데이터 분석 요청  
4. guide_request - 사용법 안내 요청
5. out_of_scope - 기능 범위 외 요청

JSON 형식: {"category": "분류", "confidence": 0.95, "reasoning": "이유"}"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                system=prompt,
                messages=[{"role": "user", "content": f"분류: {user_input}"}]
            )
            
            result = json.loads(response.content[0].text.strip())
            return {"success": True, "classification": result}
            
        except Exception as e:
            return {
                "success": True,
                "classification": {"category": "query_request", "confidence": 0.5, "reasoning": "분류 실패"}
            }
    
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None) -> dict:
        try:
            prompt = f"""BigQuery SQL 전문가로서 자연어를 SQL로 변환하세요.

프로젝트: {project_id}
기본 테이블: `nlq-ex.test_dataset.events_20210131`

규칙:
- 테이블명 언급 없으면 기본 테이블 사용
- 백틱(`) 필수 사용
- LIMIT으로 결과 제한
- SQL만 반환, 설명 제외"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=prompt,
                messages=[{"role": "user", "content": question}]
            )
            
            sql = self._clean_sql(response.content[0].text.strip())
            return {"success": True, "sql": sql}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_out_of_scope(self, question: str) -> dict:
        try:
            prompt = f"""사용자가 범위 외 질문을 했습니다: {question}

간결하게 답변:
1. 도움 불가 안내
2. BigQuery Assistant 주요 기능 (3개)
3. 예시 질문 (2개)"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return {"success": True, "response": response.content[0].text.strip()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_metadata_response(self, question: str, metadata: dict) -> dict:
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
- 행 수: {table_info.get('num_rows', 'N/A')}
- 크기: {table_info.get('size_mb', 'N/A')} MB
- 생성일: {table_info.get('created', 'N/A')}

스키마 (상위 10개 컬럼):
{schema_text}

사용자 질문: {question}

간결하고 이해하기 쉽게 답변해주세요."""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return {"success": True, "response": response.content[0].text.strip()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _clean_sql(self, sql: str) -> str:
        """SQL 정리"""
        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0]
        elif '```' in sql:
            sql = sql.split('```')[1]
        
        sql = sql.strip()
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def analyze_data(self, question: str, previous_data: list = None, previous_sql: str = None) -> dict:
        try:
            context = ""
            if previous_data and previous_sql:
                sample = previous_data[:3]
                context = f"SQL: {previous_sql}\n데이터: {json.dumps(sample, ensure_ascii=False)}\n총 {len(previous_data)}행"
            
            prompt = f"""BigQuery 데이터를 간결하게 분석:
{context}

질문: {question}

간단히 답변:
1. 주요 특징 (2개)
2. 핵심 인사이트 (1개)
3. 추가 분석 제안 (1개)"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return {"success": True, "analysis": response.content[0].text.strip()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_guide(self, question: str, context: str = "") -> dict:
        try:
            prompt = f"""BigQuery Assistant 가이드를 간결하게 제공:

상황: {context}
질문: {question}

간단히 답변:
1. 주요 기능 (3개)
2. 추천 단계 (1-2개)  
3. 예시 질문 (3개)"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return {"success": True, "guide": response.content[0].text.strip()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_out_of_scope(self, question: str) -> dict:
        try:
            prompt = f"""사용자가 범위 외 질문을 했습니다: {question}

간결하게 답변:
1. 도움 불가 안내
2. BigQuery Assistant 주요 기능 (3개)
3. 예시 질문 (2개)"""

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return {"success": True, "response": response.content[0].text.strip()}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @abstractmethod
    def generate_out_of_scope(self, question: str) -> dict:
        """범위 외 응답 생성"""
        pass
        """SQL 정리"""
        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0]
        elif '```' in sql:
            sql = sql.split('```')[1]
        
        sql = sql.strip()
        if not sql.endswith(';'):
            sql += ';'
        
        return sql


class LLMClientFactory:
    """LLM 클라이언트 팩토리"""
    
    @staticmethod
    def create_client(provider: str, config: dict) -> BaseLLMClient:
        """LLM 클라이언트 생성"""
        if provider == "anthropic":
            return AnthropicLLMClient(config["api_key"])
        else:
            raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider}")