"""
Fallback Prompts
프롬프트 템플릿이 로드되지 않았을 때 사용되는 기본 프롬프트
"""

class FallbackPrompts:
    """Fallback 프롬프트 모음"""
    
    @staticmethod
    def classification() -> str:
        """분류 프롬프트 Fallback"""
        return """사용자 입력을 다음 카테고리로 분류하고 JSON으로 응답:
                    1. query_request - 데이터 조회 요청
                    2. data_analysis - 데이터 분석 요청
                    3. guide_request - 사용법 요청
                    4. out_of_scope - 기능 범위 외

                    JSON 형식: {"category": "분류", "confidence": 0.95}"""
    
    @staticmethod
    def sql_system(project_id: str, default_table: str) -> str:
        """SQL 생성 시스템 프롬프트 Fallback"""
        return f"""BigQuery SQL 전문가로서 자연어를 SQL로 변환해주세요.

## MetaSync 데이터 (JSON)
{{"default_table": "{default_table}", "project_id": "{project_id}"}}

## 기본 규칙
- SQL만 반환, 세미콜론 필수
- LIMIT 100 기본 적용
- TIMESTAMP_MICROS(event_timestamp) 사용"""
    
    @staticmethod
    def analysis(question: str, data_context: str) -> str:
        """데이터 분석 프롬프트 Fallback"""
        return f"""다음 데이터를 분석해주세요:
                {data_context}
                질문: {question}
                주요 특징과 인사이트를 제공해주세요."""
    
    @staticmethod
    def guide(question: str, context: str) -> str:
        """가이드 프롬프트 Fallback"""
        return f"""BigQuery Assistant 사용법을 안내해주세요.
                상황: {context}
                질문: {question}
                주요 기능과 사용 예시를 제공해주세요."""
    
    @staticmethod
    def out_of_scope(question: str) -> str:
        """범위 외 응답 Fallback"""
        return f"""죄송합니다. '{question}' 질문은 BigQuery Assistant의 기능 범위를 벗어납니다.
                대신 데이터 조회, 분석, 테이블 정보 요청 등을 도와드릴 수 있습니다."""
    
    @staticmethod
    def explain(sql_query: str, question: str) -> str:
        """SQL 설명 프롬프트 Fallback"""
        return f"""다음 SQL을 설명해주세요:
                원본 질문: {question}
                SQL: {sql_query}
                쿼리의 목적과 결과를 설명해주세요."""
    
    @staticmethod
    def improvement(sql_query: str) -> str:
        """SQL 개선 프롬프트 Fallback"""
        return f"""다음 SQL의 개선 방안을 제안해주세요:
                {sql_query}
                성능, 비용, 가독성 관점에서 개선안을 제시해주세요."""
    
    @staticmethod
    def sample_questions(project_id: str, dataset_info: str) -> str:
        """샘플 질문 프롬프트 Fallback"""
        return f"""프로젝트 {project_id}에서 사용할 수 있는 유용한 질문 예시를 JSON 배열로 제공해주세요.
                {dataset_info}
                기본 조회, 집계, 분석 등 다양한 질문을 포함해주세요."""