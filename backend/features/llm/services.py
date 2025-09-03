"""
LLM Service
LLM 관련 비즈니스 로직을 담당하는 서비스
"""

import json
from typing import Dict, Any, List, Optional
from core.llm.interfaces import BaseLLMRepository, LLMRequest
from core.prompts import prompt_manager
from core.prompts.fallbacks import FallbackPrompts
from core.models.context import ContextBlock, context_blocks_to_llm_format
from core.config.llm_config import LLMConfigManager
from utils.logging_utils import get_logger
from utils.metasync_cache_loader import get_metasync_cache_loader
from .models import (
    ClassificationRequest, ClassificationResponse,
    SQLGenerationRequest, SQLGenerationResponse,
    AnalysisRequest, AnalysisResponse,
    GuideRequest, OutOfScopeRequest
)
from .utils import (
    clean_sql_response, 
    format_conversation_context, 
    extract_json_from_response,
    sanitize_error_message
)

logger = get_logger(__name__)


class LLMService:
    """LLM 비즈니스 로직 서비스"""
    
    def __init__(self, repository: BaseLLMRepository, cache_loader=None, config_manager: Optional[LLMConfigManager] = None):
        """
        LLM Service 초기화
        
        Args:
            repository: LLM Repository 인스턴스
            cache_loader: MetaSync 캐시 로더 (선택적)
            config_manager: LLM 설정 관리자 (선택적)
        """
        self.repository = repository
        self.cache_loader = cache_loader or get_metasync_cache_loader()
        self.config_manager = config_manager or LLMConfigManager()
        logger.info("✅ LLMService 초기화 완료 (설정 관리자 포함)")
    
    def classify_input(self, request: ClassificationRequest) -> ClassificationResponse:
        """
        사용자 입력 분류
        """
        try:
            # 프롬프트 템플릿 로드
            system_prompt = prompt_manager.get_prompt(
                category='classification',
                template_name='system_prompt',
                fallback_prompt=FallbackPrompts.classification()
            )
            
            # ContextBlock을 LLM 형식으로 변환
            context_blocks_formatted = ""
            if request.context_blocks:
                context_blocks_formatted = self._format_context_blocks_for_prompt(request.context_blocks)
            else:
                context_blocks_formatted = "[이전 대화 없음]"
            
            user_prompt = prompt_manager.get_prompt(
                category='classification',
                template_name='user_prompt',
                user_input=request.user_input,
                context_blocks=context_blocks_formatted,
                fallback_prompt=f"다음 입력을 분류해주세요: {request.user_input}"
            )
            
            # 설정 관리자에서 classification 설정 가져오기
            config = self.config_manager.get_config('classification')
            
            # LLM 요청 생성
            llm_request = LLMRequest(
                model=config.model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            # LLM 호출
            response = self.repository.execute_prompt(llm_request)
            
            # JSON 응답 파싱
            result_data = extract_json_from_response(response.content)
            
            if result_data and isinstance(result_data, dict):
                # 설정에서 confidence 임계값 가져오기
                config_confidence = config.confidence or 0.5
                response_confidence = float(result_data.get('confidence', config_confidence))
                
                return ClassificationResponse(
                    category=result_data.get('category', 'unknown'),
                    confidence=response_confidence,
                    reasoning=result_data.get('reasoning')
                )
            else:
                logger.warning("분류 응답을 파싱할 수 없음, 기본값 사용")
                config_confidence = config.confidence or 0.5
                return ClassificationResponse(
                    category='query_request',
                    confidence=config_confidence,
                    reasoning="파싱 실패"
                )
                
        except Exception as e:
            logger.error(f"입력 분류 중 오류: {sanitize_error_message(str(e))}")
            # 오류 시 낮은 confidence 사용
            return ClassificationResponse(
                category='query_request',
                confidence=0.1,
                reasoning=f"오류 발생: {str(e)}"
            )
    
    def generate_sql(self, request: SQLGenerationRequest) -> SQLGenerationResponse:
        """
        SQL 생성
        """
        try:
            # ContextBlock을 프롬프트용 형식으로 변환
            context_blocks_formatted = ""
            if request.context_blocks:
                context_blocks_formatted = self._format_context_blocks_for_prompt(request.context_blocks)
            else:
                context_blocks_formatted = "[이전 대화 없음]"
            
            # MetaSync 데이터로 템플릿 변수 준비
            template_vars = self._prepare_sql_template_variables(request, context_blocks_formatted)
            
            # 통합된 시스템 프롬프트 사용 (MetaSync 통합 정보)
            system_prompt = prompt_manager.get_prompt(
                category='sql_generation',
                template_name='system_prompt',
                metasync_info=template_vars['metasync_info'],
                context_blocks=template_vars['context_blocks'],
                fallback_prompt=FallbackPrompts.sql_system(request.project_id, request.default_table)
            )
            
            # 통합된 사용자 프롬프트 사용
            user_prompt = prompt_manager.get_prompt(
                category='sql_generation',
                template_name='user_prompt',
                question=template_vars['question'],
                fallback_prompt=f"다음 질문에 대한 SQL을 생성해주세요: {request.user_question}"
            )
            
            # 설정 관리자에서 sql_generation 설정 가져오기
            config = self.config_manager.get_config('sql_generation')
            
            # LLM 요청
            llm_request = LLMRequest(
                model=config.model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            response = self.repository.execute_prompt(llm_request)
            
            # SQL 정리
            cleaned_sql = clean_sql_response(response.content)
            
            # 설정에서 confidence 가져오기
            sql_confidence = config.confidence or 0.8
            
            return SQLGenerationResponse(
                sql_query=cleaned_sql,
                explanation=None,  # 필요시 별도 추출 로직 구현
                confidence=sql_confidence
            )
            
        except Exception as e:
            logger.error(f"SQL 생성 중 오류: {sanitize_error_message(str(e))}")
            raise
    
    def analyze_data(self, request: AnalysisRequest) -> AnalysisResponse:
        """
        데이터 분석 - ContextBlock을 완전한 컨텍스트 단위로 처리
        """
        try:
            # ContextBlock을 완전한 컨텍스트 단위로 처리
            context_json = self._prepare_analysis_context_json(request.context_blocks)
            
            # 프롬프트 준비
            system_prompt = prompt_manager.get_prompt(
                category='data_analysis',
                template_name='system_prompt',
                fallback_prompt="데이터를 분석하고 인사이트를 제공하는 전문가입니다."
            )
            
            # ContextBlock 완전한 단위로 전달 (설계 원칙 준수)
            user_prompt = prompt_manager.get_prompt(
                category='data_analysis',
                template_name='user_prompt',
                context_json=context_json,  # 단일 변수로 통합
                question=request.user_question,
                fallback_prompt=FallbackPrompts.analysis(request.user_question, context_json)
            )
            
            # 설정 관리자에서 data_analysis 설정 가져오기
            config = self.config_manager.get_config('data_analysis')
            
            # LLM 요청
            llm_request = LLMRequest(
                model=config.model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            response = self.repository.execute_prompt(llm_request)
            
            return AnalysisResponse(
                analysis=response.content,
                insights=None,  # 필요시 구조화 로직 추가
                recommendations=None
            )
            
        except Exception as e:
            logger.error(f"데이터 분석 중 오류: {sanitize_error_message(str(e))}")
            raise
    
    def generate_guide(self, request: GuideRequest) -> str:
        """
        가이드 생성
        """
        try:
            user_prompt = prompt_manager.get_prompt(
                category='guides',
                template_name='usage_guide',
                question=request.question,
                context=request.context or "",
                fallback_prompt=FallbackPrompts.guide(request.question, request.context or "")
            )
            
            # 설정 관리자에서 guide_generation 설정 가져오기
            config = self.config_manager.get_config('guide_generation')
            
            llm_request = LLMRequest(
                model=config.model_id,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            response = self.repository.execute_prompt(llm_request)
            return response.content
            
        except Exception as e:
            logger.error(f"가이드 생성 중 오류: {sanitize_error_message(str(e))}")
            raise
    
    def generate_out_of_scope(self, request: OutOfScopeRequest) -> str:
        """
        범위 외 응답 생성
        """
        try:
            user_prompt = prompt_manager.get_prompt(
                category='guides',
                template_name='out_of_scope',
                question=request.question,
                detected_intent=request.detected_intent or "",
                fallback_prompt=FallbackPrompts.out_of_scope(request.question)
            )
            
            # 설정 관리자에서 out_of_scope 설정 가져오기
            config = self.config_manager.get_config('out_of_scope')
            
            llm_request = LLMRequest(
                model=config.model_id, 
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            response = self.repository.execute_prompt(llm_request)
            return response.content
            
        except Exception as e:
            logger.error(f"범위 외 응답 생성 중 오류: {sanitize_error_message(str(e))}")
            return f"죄송합니다. '{request.question}' 질문은 현재 지원하지 않는 기능입니다."
    
    def _prepare_sql_template_variables(self, request: 'SQLGenerationRequest', context_blocks_formatted: str) -> Dict[str, str]:
        """
        SQL 생성 템플릿을 위한 변수 준비 (JSON 데이터 직접 문자열 변환)
        """
        try:
            # 기본 변수
            template_vars = {
                'context_blocks': context_blocks_formatted,
                'question': request.user_question,
                'metasync_info': ''
            }
            
            # MetaSync JSON 데이터를 직접 문자열로 변환
            if self.cache_loader:
                cache_data = self.cache_loader._get_cache_data()
                
                # JSON을 그대로 문자열로 변환
                import json
                metasync_info = json.dumps(cache_data, ensure_ascii=False, indent=2)
                template_vars['metasync_info'] = metasync_info
                logger.info(f"MetaSync 캐시 데이터를 JSON 문자열로 직접 전달 ({len(metasync_info)} chars)")
            else:
                # MetaSync 없을 때 기본 정보
                template_vars['metasync_info'] = f'{{"default_table": "{request.default_table}"}}'
            
            return template_vars
            
        except Exception as e:
            logger.warning(f"SQL 템플릿 변수 준비 중 오류: {str(e)}")
            return {
                'context_blocks': context_blocks_formatted,
                'question': request.user_question,
                'metasync_info': f'{{"default_table": "{request.default_table}"}}'
            }
    
    def _prepare_analysis_context_json(self, context_blocks: List[ContextBlock]) -> str:
        """
        데이터 분석을 위한 context_json 준비 - ContextBlock 설계 의도 완전 준수
        ContextBlock 모델의 유틸리티 함수 적극 활용
        """
        try:
            # ContextBlock 모델의 전용 유틸리티 함수 활용
            from core.models.context import create_analysis_context
            context_data = create_analysis_context(context_blocks)
            
            # List[ContextBlock]를 직렬화 가능한 형태로 변환
            from core.models.context import context_blocks_to_complete_format
            context_data["context_blocks"] = context_blocks_to_complete_format(context_data["context_blocks"])
            
            # 로깅
            row_count = context_data["meta"]["total_row_count"]  
            if row_count > 0:
                logger.info(f"📊 분석용 데이터 추출 완료: {row_count}개 행")
            
            return json.dumps(context_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.warning(f"분석 컨텍스트 JSON 준비 중 오류: {str(e)}")
            return '{"context_blocks": [], "meta": {"total_row_count": 0, "blocks_count": 0}, "limits": {"max_rows": 100}}'
    
    def is_available(self) -> bool:
        """
        서비스 가용성 확인
        """
        return self.repository.is_available()
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보 조회
        """
        return self.repository.get_model_info()
    
    def _format_context_blocks_for_prompt(self, context_blocks: List[ContextBlock]) -> str:
        """
        ContextBlock 리스트를 프롬프트용 문자열로 변환 (완전한 컨텍스트 포함)
        대화 + 쿼리 + 실행결과 메타정보까지 포함하는 완전한 컨텍스트
        """
        if not context_blocks:
            return "[이전 대화 없음]"
        
        # ContextBlock 모델의 유틸리티 함수 활용
        from core.models.context import context_blocks_to_llm_format
        recent_blocks = context_blocks[-5:]  # 최근 5개만
        llm_messages = context_blocks_to_llm_format(recent_blocks)
        
        formatted_parts = []
        conversation_idx = 1
        
        for msg in llm_messages:
            role = "사용자" if msg["role"] == "user" else "AI"
            base_msg = f"[{conversation_idx}] {role}: {msg['content']}"
            
            # AI 응답의 경우 실행 통계 정보 추가
            if msg["role"] == "assistant" and "metadata" in msg:
                execution_info = []
                
                # 생성된 쿼리 정보
                if msg["metadata"].get("generated_query"):
                    execution_info.append(f"SQL: {msg['metadata']['generated_query']}")
                
                # 실행 결과 행 수 정보  
                if msg.get("query_row_count", 0) > 0:
                    execution_info.append(f"결과: {msg['query_row_count']}개 행")
                
                if execution_info:
                    base_msg += f" ({', '.join(execution_info)})"
                
                conversation_idx += 1
            
            formatted_parts.append(base_msg)
        
        return "\n".join(formatted_parts) if formatted_parts else "[이전 대화 없음]"