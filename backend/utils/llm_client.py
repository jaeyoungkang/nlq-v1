"""
통합 LLM 클라이언트 - 프롬프트 중앙 관리 시스템 적용
리팩토링: 하드코딩된 프롬프트를 JSON 파일 기반 시스템으로 교체
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import anthropic

# 프롬프트 중앙 관리 시스템 임포트
from .prompts import prompt_manager

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
    """Anthropic Claude LLM 클라이언트 - 프롬프트 중앙 관리 버전"""
    
    def __init__(self, api_key: str):
        """
        Anthropic 클라이언트 초기화
        
        Args:
            api_key: Anthropic API 키
        """
        self.api_key = api_key
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("✅ Anthropic LLM 클라이언트 초기화 완료 (프롬프트 중앙 관리)")
        except Exception as e:
            logger.error(f"❌ Anthropic 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def classify_input(self, user_input: str) -> dict:
        """
        사용자 입력을 카테고리별로 분류 (프롬프트 중앙 관리 적용)
        
        Args:
            user_input: 사용자 입력 텍스트
            
        Returns:
            분류 결과 딕셔너리
        """
        try:
            # 프롬프트 중앙 관리 시스템에서 로드
            system_prompt = prompt_manager.get_prompt(
                category='classification',
                template_name='system_prompt',
                fallback_prompt=self._get_fallback_classification_prompt()
            )
            
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
        자연어 질문을 BigQuery SQL로 변환 (프롬프트 중앙 관리 적용)
        
        Args:
            question: 사용자의 자연어 질문
            project_id: BigQuery 프로젝트 ID  
            dataset_ids: 사용할 데이터셋 ID 목록 (선택사항)
            
        Returns:
            SQL 생성 결과
        """
        try:
            # 프롬프트 중앙 관리 시스템에서 시스템 프롬프트 생성
            system_prompt = self._create_sql_system_prompt_from_templates(project_id, dataset_ids)
            
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
            
            logger.info(f"🔧 SQL 생성 완료 (중앙 관리): {cleaned_sql[:100]}...")
            
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
        메타데이터 기반 응답 생성 (프롬프트 중앙 관리 적용)
        
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
            
            # 프롬프트 중앙 관리 시스템에서 로드
            prompt = prompt_manager.get_prompt(
                category='data_analysis',
                template_name='metadata_response',
                table_id=table_info.get('table_id', 'nlq-ex.test_dataset.events_20210131'),
                row_count=f"{table_info.get('num_rows', 'N/A'):,}" if table_info.get('num_rows') else 'N/A',
                size_mb=table_info.get('size_mb', 'N/A'),
                created_date=table_info.get('created', 'N/A'),
                schema_text=schema_text,
                user_question=question,
                fallback_prompt=self._get_fallback_metadata_prompt(question, table_info, schema_text)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            logger.info(f"📋 메타데이터 응답 생성 완료 (중앙 관리)")
            
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
        조회된 데이터에 대한 분석 생성 (프롬프트 중앙 관리 적용)
        
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
                
                # 프롬프트 중앙 관리 시스템에서 데이터 컨텍스트 생성
                data_context = prompt_manager.get_prompt(
                    category='data_analysis',
                    template_name='data_context_template',
                    previous_sql=previous_sql,
                    data_sample=json.dumps(data_sample, indent=2, ensure_ascii=False, default=str),
                    total_rows=len(previous_data),
                    fallback_prompt=f"최근 실행된 SQL: {previous_sql}\n조회 결과: {len(previous_data)}행"
                )
            
            # 메인 분석 프롬프트 로드
            analysis_prompt = prompt_manager.get_prompt(
                category='data_analysis',
                template_name='analyze_data',
                data_context=data_context,
                user_question=question,
                fallback_prompt=self._get_fallback_analysis_prompt(question, data_context)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            analysis = response.content[0].text.strip()
            logger.info(f"🔍 데이터 분석 완료 (중앙 관리)")
            
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
        가이드 응답 생성 (프롬프트 중앙 관리 적용)
        
        Args:
            question: 사용자의 가이드 요청
            context: 현재 상황 컨텍스트
            
        Returns:
            가이드 응답 결과
        """
        try:
            # 프롬프트 중앙 관리 시스템에서 로드
            guide_prompt = prompt_manager.get_prompt(
                category='guides',
                template_name='usage_guide',
                context=context,
                user_question=question,
                fallback_prompt=self._get_fallback_guide_prompt(question, context)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": guide_prompt}]
            )
            
            guide = response.content[0].text.strip()
            logger.info(f"💡 가이드 응답 생성 완료 (중앙 관리)")
            
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
        기능 범위 외 요청에 대한 응답 생성 (프롬프트 중앙 관리 적용)
        
        Args:
            question: 사용자의 질문
            
        Returns:
            범위 외 응답 결과
        """
        try:
            # 프롬프트 중앙 관리 시스템에서 로드
            scope_prompt = prompt_manager.get_prompt(
                category='guides',
                template_name='out_of_scope',
                user_question=question,
                fallback_prompt=self._get_fallback_out_of_scope_prompt(question)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": scope_prompt}]
            )
            
            scope_response = response.content[0].text.strip()
            logger.info(f"🚫 범위 외 응답 생성 완료 (중앙 관리)")
            
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
    
    def _create_sql_system_prompt_from_templates(self, project_id: str, dataset_ids: List[str] = None) -> str:
        """프롬프트 중앙 관리 시스템에서 SQL 생성 시스템 프롬프트 생성"""
        
        default_table = "`nlq-ex.test_dataset.events_20210131`"
        
        try:
            # 기본 데이터셋 정보 생성
            dataset_info = prompt_manager.get_prompt(
                category='sql_generation',
                template_name='dataset_info_template',
                default_table=default_table,
                fallback_prompt=""
            )
            
            # 추가 데이터셋이 있는 경우
            if dataset_ids:
                dataset_list = ", ".join([f"`{project_id}.{ds}`" for ds in dataset_ids])
                additional_datasets = prompt_manager.get_prompt(
                    category='sql_generation',
                    template_name='additional_datasets_template',
                    dataset_list=dataset_list,
                    fallback_prompt=""
                )
                dataset_info += additional_datasets
            
            # 메인 시스템 프롬프트 생성
            system_prompt = prompt_manager.get_prompt(
                category='sql_generation',
                template_name='system_prompt',
                project_id=project_id,
                dataset_info=dataset_info,
                default_table=default_table,
                fallback_prompt=self._get_fallback_sql_system_prompt(project_id, default_table)
            )
            
            return system_prompt
            
        except Exception as e:
            logger.error(f"❌ SQL 시스템 프롬프트 생성 실패: {str(e)}")
            return self._get_fallback_sql_system_prompt(project_id, default_table)
    
    def _clean_sql_response(self, raw_response: str) -> str:
        """Claude 응답에서 SQL 쿼리만 추출하고 정리 (기존 로직 유지)"""
        
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

    # === 추가 유틸리티 메서드 (프롬프트 중앙 관리 적용) ===
    
    def explain_query(self, sql_query: str, question: str) -> dict:
        """
        생성된 SQL 쿼리에 대한 설명 생성 (프롬프트 중앙 관리 적용)
        """
        try:
            explanation_prompt = prompt_manager.get_prompt(
                category='improvements',
                template_name='explain_query',
                user_question=question,
                sql_query=sql_query,
                fallback_prompt=self._get_fallback_explain_prompt(sql_query, question)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                messages=[{"role": "user", "content": explanation_prompt}]
            )
            
            explanation = response.content[0].text.strip()
            logger.info(f"📝 쿼리 설명 생성 완료 (중앙 관리)")
            
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
        SQL 쿼리 개선 사항 제안 (프롬프트 중앙 관리 적용)
        """
        try:
            improvement_prompt = prompt_manager.get_prompt(
                category='improvements',
                template_name='suggest_improvements',
                sql_query=sql_query,
                fallback_prompt=self._get_fallback_improvement_prompt(sql_query)
            )

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": improvement_prompt}]
            )
            
            suggestions = response.content[0].text.strip()
            logger.info(f"💡 쿼리 개선 제안 생성 완료 (중앙 관리)")
            
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
        프로젝트와 데이터셋을 기반으로 샘플 질문들을 생성 (프롬프트 중앙 관리 적용)
        """
        try:
            dataset_info = ""
            if dataset_ids:
                dataset_list = ", ".join(dataset_ids)
                dataset_info = f"사용 가능한 데이터셋: {dataset_list}"
            
            sample_prompt = prompt_manager.get_prompt(
                category='guides',
                template_name='sample_questions',
                project_id=project_id,
                dataset_info=dataset_info,
                fallback_prompt=self._get_fallback_sample_questions_prompt(project_id, dataset_info)
            )

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
                    logger.info(f"📝 샘플 질문 {len(questions)}개 생성 완료 (중앙 관리)")
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
        """텍스트에서 질문들을 추출하는 헬퍼 함수 (기존 로직 유지)"""
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

    # === Fallback 프롬프트들 (프롬프트 로딩 실패 시 사용) ===
    
    def _get_fallback_classification_prompt(self) -> str:
        """분류 프롬프트 Fallback"""
        return """사용자 입력을 다음 카테고리로 분류하고 JSON으로 응답:
1. query_request - 데이터 조회 요청
2. metadata_request - 테이블 정보 요청
3. data_analysis - 데이터 분석 요청
4. guide_request - 사용법 요청
5. out_of_scope - 기능 범위 외

JSON 형식: {"category": "분류", "confidence": 0.95}"""
    
    def _get_fallback_sql_system_prompt(self, project_id: str, default_table: str) -> str:
        """SQL 생성 시스템 프롬프트 Fallback"""
        return f"""BigQuery SQL 전문가로서 자연어를 SQL로 변환해주세요.
프로젝트: {project_id}
기본 테이블: {default_table}
- SQL만 반환, 세미콜론 필수
- LIMIT 100 기본 적용
- TIMESTAMP_MICROS(event_timestamp) 사용"""
    
    def _get_fallback_metadata_prompt(self, question: str, table_info: dict, schema_text: str) -> str:
        """메타데이터 응답 Fallback"""
        return f"""테이블 정보를 설명해주세요:
{table_info.get('table_id', 'Unknown')}
질문: {question}
스키마: {schema_text}"""
    
    def _get_fallback_analysis_prompt(self, question: str, data_context: str) -> str:
        """데이터 분석 프롬프트 Fallback"""
        return f"""다음 데이터를 분석해주세요:
{data_context}
질문: {question}
주요 특징과 인사이트를 제공해주세요."""
    
    def _get_fallback_guide_prompt(self, question: str, context: str) -> str:
        """가이드 프롬프트 Fallback"""
        return f"""BigQuery Assistant 사용법을 안내해주세요.
상황: {context}
질문: {question}
주요 기능과 사용 예시를 제공해주세요."""
    
    def _get_fallback_out_of_scope_prompt(self, question: str) -> str:
        """범위 외 응답 Fallback"""
        return f"""죄송합니다. '{question}' 질문은 BigQuery Assistant의 기능 범위를 벗어납니다.
대신 데이터 조회, 분석, 테이블 정보 요청 등을 도와드릴 수 있습니다."""
    
    def _get_fallback_explain_prompt(self, sql_query: str, question: str) -> str:
        """SQL 설명 프롬프트 Fallback"""
        return f"""다음 SQL을 설명해주세요:
원본 질문: {question}
SQL: {sql_query}
쿼리의 목적과 결과를 설명해주세요."""
    
    def _get_fallback_improvement_prompt(self, sql_query: str) -> str:
        """SQL 개선 프롬프트 Fallback"""
        return f"""다음 SQL의 개선 방안을 제안해주세요:
{sql_query}
성능, 비용, 가독성 관점에서 개선안을 제시해주세요."""
    
    def _get_fallback_sample_questions_prompt(self, project_id: str, dataset_info: str) -> str:
        """샘플 질문 프롬프트 Fallback"""
        return f"""프로젝트 {project_id}에서 사용할 수 있는 유용한 질문 예시를 JSON 배열로 제공해주세요.
{dataset_info}
기본 조회, 집계, 분석 등 다양한 질문을 포함해주세요."""


class LLMClientFactory:
    """LLM 클라이언트 팩토리 - 확장 가능한 구조 (프롬프트 중앙 관리 지원)"""
    
    @staticmethod
    def create_client(provider: str, config: dict) -> BaseLLMClient:
        """
        LLM 클라이언트 생성
        
        Args:
            provider: LLM 제공업체 ('anthropic', 'openai' 등)
            config: 설정 딕셔너리 (api_key 등)
            
        Returns:
            BaseLLMClient 인스턴스 (프롬프트 중앙 관리 지원)
            
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
            logger.info(f"✅ {provider} LLM 클라이언트 생성 완료 (프롬프트 중앙 관리)")
            return client
        except Exception as e:
            logger.error(f"❌ {provider} LLM 클라이언트 생성 실패: {str(e)}")
            raise