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
# MetaSync 캐시 로더 임포트
from .metasync_cache_loader import get_metasync_cache_loader
# ContextBlock 임포트
from models import ContextBlock, context_blocks_to_llm_format

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """LLM 클라이언트 추상 베이스 클래스"""
    
    @abstractmethod
    def classify_input(self, user_input: str, context_blocks: List[ContextBlock] = None) -> dict:
        """사용자 입력 분류"""
        pass
    
    @abstractmethod
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None, 
                   context_blocks: List[ContextBlock] = None) -> dict:
        """SQL 생성"""
        pass
    
    @abstractmethod
    def analyze_data(self, question: str, 
                   context_blocks: List[ContextBlock] = None) -> dict:
        """데이터 분석"""
        pass
    
    @abstractmethod
    def generate_guide(self, question: str, context: str = "") -> dict:
        """가이드 생성"""
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
            # MetaSync 캐시 로더 초기화
            self.cache_loader = get_metasync_cache_loader()
            logger.info("✅ Anthropic LLM 클라이언트 초기화 완료 (프롬프트 중앙 관리 + MetaSync)")
        except Exception as e:
            logger.error(f"❌ Anthropic 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def classify_input(self, user_input: str, context_blocks: List[ContextBlock] = None) -> dict:
        """
        사용자 입력을 카테고리별로 분류 (ContextBlock 사용)
        
        Args:
            user_input: 사용자 입력 텍스트
            context_blocks: 이전 대화 ContextBlock 리스트 (선택사항)
            
        Returns:
            분류 결과 딕셔너리
        """
        # ContextBlock을 LLM 형식으로 변환
        llm_context = context_blocks_to_llm_format(context_blocks) if context_blocks else []
        
        return self._execute_unified_prompting(
            category='classification',
            input_data={'user_input': user_input},
            context_blocks=context_blocks
        )
    
    
    def _normalize_conversation_context(self, conversation_context: List[Dict] = None) -> str:
        """컨텍스트 정규화 - 항상 문자열 반환"""
        if not conversation_context or len(conversation_context) == 0:
            return "[이전 대화 없음]"
        
        return self._format_conversation_context(conversation_context)
    
    def _calculate_dynamic_tokens(self, category: str, context: str) -> int:
        """
        컨텍스트 길이와 카테고리에 따른 지능형 토큰 할당
        """
        # 기본 토큰 설정
        base_tokens = {
            'classification': 300,     # 분류는 짧은 JSON 응답
            'sql_generation': 1200,    # SQL은 복잡한 쿼리 가능
            'data_analysis': 1200,     # 분석은 상세한 설명 필요
            'guide_request': 800,      # 가이드는 중간 길이
            'metadata_request': 600    # 메타데이터는 구조화된 응답
        }
        
        base = base_tokens.get(category, 400)
        
        # 컨텍스트 길이에 따른 추가 토큰
        if context == "[이전 대화 없음]":
            return base
        
        # 컨텍스트 길이 측정 (대략적)
        context_length = len(context.split())
        
        if context_length < 50:
            context_bonus = 50      # 짧은 컨텍스트
        elif context_length < 200:
            context_bonus = 100     # 중간 컨텍스트  
        else:
            context_bonus = 200     # 긴 컨텍스트
        
        # 카테고리별 컨텍스트 민감도
        context_multiplier = {
            'classification': 0.5,    # 분류는 컨텍스트 영향 적음
            'sql_generation': 1.0,    # SQL은 컨텍스트 중요
            'data_analysis': 1.5,     # 분석은 컨텍스트 매우 중요
            'guide_request': 0.7,
            'metadata_request': 0.3
        }
        
        multiplier = context_multiplier.get(category, 1.0)
        final_bonus = int(context_bonus * multiplier)
        
        return min(base + final_bonus, 2000)  # 최대 2000 토큰 제한

    def _execute_unified_prompting(self, 
                                 category: str,
                                 input_data: Dict[str, Any],
                                 context_blocks: List[ContextBlock] = None) -> dict:
        """
        통합 프롬프팅 실행 - 항상 같은 템플릿 사용
        
        Args:
            category: 프롬프트 카테고리
            input_data: 입력 데이터
            context_blocks: 이전 대화 ContextBlock 리스트
            
        Returns:
            LLM 응답 결과
        """
        try:
            # ContextBlock을 LLM 형식으로 변환
            llm_context = context_blocks_to_llm_format(context_blocks) if context_blocks else []
            
            # 데이터 분석: 비변형 원칙 적용 — 요약/정규화 대신 원본 JSON 전달
            if category == 'data_analysis':
                import os
                import json as _json
                # 최근 결과 RAW 행 추출 및 크기 제한 적용
                raw_rows_all = self._extract_latest_result_rows(context_blocks or [])
                max_rows = int(os.getenv('ANALYSIS_MAX_ROWS', '200'))
                max_chars = int(os.getenv('ANALYSIS_MAX_CHARS', '60000'))
                raw_rows_json = self._pack_rows_as_json(raw_rows_all, max_rows=max_rows, max_chars=max_chars)
                try:
                    raw_rows = _json.loads(raw_rows_json)
                except Exception:
                    raw_rows = []

                # 메타데이터 수집(전체 행 수/출처 블록)
                source_block_id = None
                total_row_count = None
                for blk in reversed(context_blocks or []):
                    if getattr(blk, 'execution_result', None):
                        source_block_id = getattr(blk, 'block_id', None)
                        total_row_count = blk.execution_result.get('row_count')
                        break

                # 단일 컨텍스트 JSON(envelope) 구성 — data 키는 RAW 행을 그대로 포함
                envelope = {
                    'messages': llm_context,
                    'data': raw_rows,
                    'meta': {
                        'row_count': total_row_count if total_row_count is not None else (len(raw_rows_all) if isinstance(raw_rows_all, list) else None),
                        'included_rows': len(raw_rows) if isinstance(raw_rows, list) else 0,
                        'source_block_id': source_block_id
                    },
                    'limits': {
                        'max_rows': max_rows,
                        'max_chars': max_chars
                    }
                }

                context_json = _json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))
                normalized_context = "[context-json]"
            else:
                normalized_context = self._normalize_conversation_context(llm_context)
            
            # 컨텍스트 확인 (오류 발생시에만 로그)
            context_count = len(context_blocks) if context_blocks else 0
            
            # MetaSync 캐시 데이터 통합 (SQL 생성 시에만)
            enhanced_input_data = self._enhance_input_data_with_metasync(category, input_data)
            
            # 단일 템플릿 사용 (향상된 데이터 사용)
            system_prompt = prompt_manager.get_prompt(
                category=category,
                template_name='system_prompt',
                **enhanced_input_data,
                fallback_prompt=self._get_fallback_system_prompt(category)
            )
            
            if category == 'data_analysis':
                user_prompt = prompt_manager.get_prompt(
                    category=category,
                    template_name='user_prompt',
                    context_json=context_json,
                    **enhanced_input_data,
                    fallback_prompt=self._get_fallback_user_prompt(category, enhanced_input_data)
                )
                # 데이터 분석은 충분한 토큰을 고정 할당(상한 2000)
                max_tokens = 2000
            else:
                user_prompt = prompt_manager.get_prompt(
                    category=category,
                    template_name='user_prompt',
                    context_blocks=normalized_context,
                    **enhanced_input_data,
                    fallback_prompt=self._get_fallback_user_prompt(category, enhanced_input_data)
                )
                # 동적 토큰 할당
                max_tokens = self._calculate_dynamic_tokens(category, normalized_context)
            
            # Claude API 호출
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            response_text = response.content[0].text.strip()
            return self._post_process_response(category, response_text, normalized_context)
            
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            logger.warning(f"⚠️ Anthropic API 속도 제한 또는 과부하: {str(e)}")
            return {
                "success": False,
                "error": "AI 서비스가 일시적으로 요청이 많아 응답할 수 없습니다. 잠시 후 다시 시도해주세요.",
                "error_type": "rate_limit_error"
            }
        except Exception as e:
            logger.error(f"❌ 통합 프롬프팅 오류 ({category}): {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_latest_result_rows(self, blocks: List[ContextBlock]) -> List[Dict[str, Any]]:
        """가장 최근 ContextBlock에서 RAW 결과 행을 추출(비변형)"""
        try:
            for blk in reversed(blocks):
                if getattr(blk, 'execution_result', None):
                    data = blk.execution_result.get('data')
                    if isinstance(data, list) and data:
                        return data
            return []
        except Exception:
            return []

    def _pack_rows_as_json(self, rows: List[Dict[str, Any]], max_rows: int = 200, max_chars: int = 60000) -> str:
        """RAW 행 리스트를 JSON 문자열로 직렬화(무손실, 크기 제한만 적용)"""
        import json as _json
        if not rows:
            return "[]"
        n = min(len(rows), max_rows)
        while n >= 1:
            chunk = rows[:n]
            s = _json.dumps(chunk, ensure_ascii=False, separators=(',', ':'))
            if len(s) <= max_chars:
                return s
            # 크기 초과 시 행 수를 줄여 재시도(70% 비율로 감소)
            new_n = int(n * 0.7)
            n = new_n if new_n < n else n - 1
        # 최소 1행도 초과하면 빈 배열 반환
        return "[]"

    def _format_analysis_context(self, context_messages: List[Dict[str, Any]]) -> str:
        """데이터 분석용으로 컨텍스트를 풍부하게 요약 (결과 샘플 포함)

        - 최근 메시지 5개 내에서, assistant의 쿼리 결과가 있으면 컬럼과 상위 2행을 포함
        - 길이 제한을 위해 각 행은 최대 3개 컬럼만 표시
        """
        if not context_messages:
            return "[이전 대화 없음]"

        lines: List[str] = []
        # 최근 5개 메시지만 고려
        msgs = context_messages[-5:]
        for msg in msgs:
            role = "사용자" if msg.get('role') == 'user' else 'AI'
            timestamp = msg.get('timestamp', '')[:19] if msg.get('timestamp') else ''
            content = msg.get('content', '') or ''
            if len(content) > 200:
                content = content[:200] + '...'

            # 기본 라인
            base = f"[{timestamp}] {role}: {content}"

            # 분석에 유용한 부가 정보 (assistant 쪽 결과 요약)
            sample_added = False
            if role == 'AI':
                row_count = msg.get('query_row_count') or 0
                if row_count:
                    base += f" (결과 {row_count}행)"
                result_rows = msg.get('query_result_data')
                if isinstance(result_rows, list) and result_rows:
                    # 컬럼 추출 및 상위 2행 샘플
                    first_row = result_rows[0]
                    if isinstance(first_row, dict):
                        columns = list(first_row.keys())[:3]
                        lines.append(base)
                        lines.append(f"  ▷ 컬럼: {', '.join(columns)}")
                        # 최대 2행 샘플
                        for i, row in enumerate(result_rows[:2]):
                            row_vals = [str(row.get(c)) for c in columns]
                            lines.append(f"  ▷ 샘플행{i+1}: {', '.join(row_vals)}")
                        sample_added = True
            if not sample_added:
                lines.append(base)

        return "\n".join(lines) if lines else "[이전 대화 없음]"

    def _format_conversation_context(self, context: List[Dict]) -> str:
        """대화 컨텍스트를 LLM 프롬프트용 텍스트로 변환"""
        if not context:
            return ""
        
        formatted_lines = []
        for msg in context[-3:]:  # 최근 5개 메시지만 사용
            role = "사용자" if msg['role'] == "user" else "AI"
            timestamp = msg.get('timestamp', '')[:19] if msg.get('timestamp') else ''
            content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
            
            # SQL 정보가 있는 경우 추가
            sql_info = ""
            if msg.get('metadata', {}).get('generated_sql'):
                sql_info = f" [SQL 생성함]"
            
            formatted_lines.append(f"[{timestamp}] {role}: {content}{sql_info}")
        
        return "\n".join(formatted_lines)
    
    # 카테고리별 컨텍스트 처리기들
    def _process_classification_context(self, context: List[Dict]) -> Dict[str, Any]:
        """분류용 컨텍스트 처리"""
        return {'conversation_context': self._format_conversation_context(context)}
    
    def _process_sql_context(self, context: List[Dict]) -> Dict[str, Any]:
        """SQL 생성용 컨텍스트 처리"""
        return {
            'conversation_context': self._format_conversation_context(context),
            'previous_sqls': self._extract_sql_patterns(context),
            'frequently_used_tables': self._extract_table_usage(context)
        }
    
    def _process_analysis_context(self, context: List[Dict]) -> Dict[str, Any]:
        """분석용 컨텍스트 처리"""
        return {
            'conversation_context': self._format_conversation_context(context),
            'previous_analysis': self._extract_previous_analysis(context)
        }
    
    def _extract_sql_patterns(self, context: List[Dict]) -> str:
        """이전 대화에서 SQL 패턴 추출"""
        sql_patterns = []
        for msg in context:
            if msg.get('metadata', {}).get('generated_sql'):
                sql = msg['metadata']['generated_sql']
                if sql and len(sql) > 20:
                    sql_patterns.append(sql[:100] + "...")
        
        return "\n".join(sql_patterns) if sql_patterns else "이전 SQL 없음"
    
    def _extract_table_usage(self, context: List[Dict]) -> str:
        """자주 사용되는 테이블 패턴 추출"""
        tables = []
        for msg in context:
            if msg.get('metadata', {}).get('generated_sql'):
                sql = msg['metadata']['generated_sql']
                if sql and 'FROM' in sql.upper():
                    # 간단한 테이블명 추출
                    import re
                    table_matches = re.findall(r'FROM\s+`([^`]+)`', sql, re.IGNORECASE)
                    tables.extend(table_matches)
        
        unique_tables = list(set(tables))
        return ", ".join(unique_tables) if unique_tables else "기본 테이블 사용"
    
    def _extract_previous_analysis(self, context: List[Dict]) -> str:
        """이전 분석 결과 추출"""
        analyses = []
        for msg in context:
            if msg['role'] == 'assistant' and '분석' in msg['content']:
                analyses.append(msg['content'][:150] + "...")
        
        return "\n".join(analyses) if analyses else "이전 분석 없음"
    
    def _post_process_response(self, category: str, response_text: str, normalized_context: str) -> dict:
        """카테고리별 응답 후처리"""
        if category == 'classification':
            try:
                classification = json.loads(response_text)
                if all(key in classification for key in ["category", "confidence"]):
                    context_info = f" (컨텍스트: 있음)" if normalized_context != "[이전 대화 없음]" else " (컨텍스트: 없음)"
                    logger.info(f"🎯 통합 분류: {classification['category']}{context_info}")
                    return {"success": True, "classification": classification}
                else:
                    raise ValueError("필수 필드 누락")
            except (json.JSONDecodeError, ValueError):
                return {
                    "success": True,
                    "classification": {
                        "category": "query_request",
                        "confidence": 0.5,
                        "reasoning": "통합 분류 파싱 실패로 기본값 사용"
                    }
                }
        elif category == 'sql_generation':
            cleaned_sql = self._clean_sql_response(response_text)
            logger.info(f"🔧 통합 SQL 생성 완료: {cleaned_sql[:100]}...")
            return {
                "success": True,
                "sql": cleaned_sql,
                "raw_response": response_text
            }
        elif category == 'data_analysis':
            logger.info(f"🔍 통합 데이터 분석 완료")
            return {
                "success": True,
                "analysis": response_text
            }
        else:
            return {
                "success": True,
                "response": response_text
            }
    
    def _get_fallback_system_prompt(self, category: str) -> str:
        """카테고리별 시스템 프롬프트 Fallback"""
        fallbacks = {
            'classification': self._get_fallback_classification_prompt(),
            'sql_generation': "BigQuery SQL 전문가로서 자연어를 SQL로 변환해주세요.",
            'data_analysis': "데이터 분석 전문가로서 주어진 데이터를 분석해주세요."
        }
        return fallbacks.get(category, "전문 AI 어시스턴트로서 도움을 제공해주세요.")
    
    def _get_fallback_user_prompt(self, category: str, input_data: Dict[str, Any]) -> str:
        """카테고리별 사용자 프롬프트 Fallback"""
        if category == 'classification':
            return f"분류할 입력: {input_data.get('user_input', '')}"
        elif category == 'sql_generation':
            return f"SQL 생성 질문: {input_data.get('question', '')}"
        elif category == 'data_analysis':
            return f"분석 질문: {input_data.get('question', '')}"
        else:
            return str(input_data)
    
    def generate_sql(self, question: str, project_id: str, dataset_ids: list = None, 
                   context_blocks: List[ContextBlock] = None) -> dict:
        """
        자연어 질문을 BigQuery SQL로 변환 (ContextBlock 사용)
        
        Args:
            question: 사용자의 자연어 질문
            project_id: BigQuery 프로젝트 ID  
            dataset_ids: 사용할 데이터셋 ID 목록 (선택사항)
            context_blocks: 이전 대화 ContextBlock 리스트 (선택사항)
            
        Returns:
            SQL 생성 결과
        """
        default_table = "`nlq-ex.test_dataset.events_20210131`"
        
        # ContextBlock을 LLM 형식으로 변환
        llm_context = context_blocks_to_llm_format(context_blocks) if context_blocks else []
        
        return self._execute_unified_prompting(
            category='sql_generation',
            input_data={
                'question': question,
                'project_id': project_id,
                'default_table': default_table
            },
            context_blocks=context_blocks
        )

    def analyze_data(self, question: str, context_blocks: List[ContextBlock] = None) -> dict:
        """
        컨텍스티 기반 분석 생성
        
        Args:
            question: 사용자의 분석 요청 질문
            context_blocks: 이전 대화 ContextBlock 리스트
            
        Returns:
            데이터 분석 결과
        """
        
        # 비변형 원칙: 전체 컨텍스트 사용 (자르기/청크는 이후 단계에서 처리)
        recent_blocks = context_blocks or []
        
        # 블록 정보 로깅
        if recent_blocks:
            logger.info(f"🧩 분석용 컨텍스트: {len(recent_blocks)}개 블록")
        
        # ContextBlock을 LLM 형식으로 변환 (원본 형태 유지)
        llm_context = context_blocks_to_llm_format(recent_blocks) if recent_blocks else []

        return self._execute_unified_prompting(
            category='data_analysis',
            input_data={
                'question': question
            },
            context_blocks=recent_blocks
        )

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

    # === MetaSync 캐시 통합 메서드들 ===
    
    def _enhance_input_data_with_metasync(self, category: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        카테고리에 따라 MetaSync 캐시 데이터를 input_data에 통합
        
        Args:
            category: 프롬프트 카테고리
            input_data: 기존 입력 데이터
            
        Returns:
            MetaSync 데이터가 통합된 입력 데이터
        """
        enhanced_data = input_data.copy()
        
        # SQL 생성 관련 카테고리에서만 MetaSync 데이터 활용
        if category in ['query_request', 'sql_generation']:
            try:
                cached_data = self._get_cached_data_with_fallback()
                
                if cached_data['source'] == 'metasync':
                    pass  # MetaSync 데이터 적용
                    
                    # 스키마 정보 추가
                    enhanced_data['schema_columns'] = self._format_schema_for_prompt(
                        cached_data['schema_info'].get('columns', [])
                    )
                    
                    # Few-Shot 예시 추가
                    enhanced_data['few_shot_examples'] = self._format_examples_for_prompt(
                        cached_data['examples']
                    )
                    
                    # 테이블 ID 추가
                    enhanced_data['table_id'] = cached_data['schema_info'].get(
                        'table_id', 'nlq-ex.test_dataset.events_20210131'
                    )
                    
                else:
                    logger.warning("⚠️ MetaSync 캐시 사용 불가, 폴백 데이터 사용")
                    enhanced_data.update(self._get_fallback_metasync_data())
                    
            except Exception as e:
                logger.error(f"❌ MetaSync 데이터 통합 실패: {e}")
                enhanced_data.update(self._get_fallback_metasync_data())
        
        return enhanced_data
    
    def _get_cached_data_with_fallback(self) -> Dict[str, Any]:
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
    
    def _get_fallback_data(self) -> Dict[str, Any]:
        """캐시 로드 실패 시 기본 데이터 반환"""
        return {
            'schema_info': {
                'table_id': 'nlq-ex.test_dataset.events_20210131',
                'columns': []  # 빈 스키마로 처리
            },
            'examples': [],  # 빈 예시로 처리
            'source': 'fallback'
        }
    
    def _get_fallback_metasync_data(self) -> Dict[str, Any]:
        """MetaSync 폴백 데이터"""
        return {
            'schema_columns': "스키마 정보를 로드할 수 없습니다. 기본 테이블 구조를 가정합니다.",
            'few_shot_examples': "예시를 로드할 수 없습니다. 기본 쿼리 패턴을 사용합니다.",
            'table_id': 'nlq-ex.test_dataset.events_20210131'
        }
    
    def _format_schema_for_prompt(self, columns: List[Dict[str, str]]) -> str:
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
    
    def _format_examples_for_prompt(self, examples: List[Dict[str, str]]) -> str:
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
    
    def check_metasync_status(self) -> Dict[str, Any]:
        """MetaSync 캐시 상태 확인 (디버깅/모니터링용)"""
        try:
            metadata = self.cache_loader.get_cache_metadata()
            return {
                'status': 'available' if self.cache_loader.is_cache_available() else 'unavailable',
                'generated_at': metadata.get('generated_at'),
                'examples_count': metadata.get('examples_count', 0),
                'columns_count': metadata.get('columns_count', 0),
                'table_id': metadata.get('table_id')
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    # === Fallback 프롬프트들 (프롬프트 로딩 실패 시 사용) ===
    
    def _get_fallback_classification_prompt(self) -> str:
        """분류 프롬프트 Fallback"""
        return """사용자 입력을 다음 카테고리로 분류하고 JSON으로 응답:
                    1. query_request - 데이터 조회 요청
                    2. data_analysis - 데이터 분석 요청
                    3. guide_request - 사용법 요청
                    4. out_of_scope - 기능 범위 외

                    JSON 형식: {"category": "분류", "confidence": 0.95}"""
    
    def _get_fallback_sql_system_prompt(self, project_id: str, default_table: str) -> str:
        """SQL 생성 시스템 프롬프트 Fallback"""
        return f"""BigQuery SQL 전문가로서 자연어를 SQL로 변환해주세요.
            프로젝트: {project_id}
            기본 테이블: {default_table}
            - SQL만 반환, 세미콜론 필수
            - LIMIT 100 기본 적용
            - TIMESTAMP_MICROS(event_timestamp) 사용"""
    
    
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
