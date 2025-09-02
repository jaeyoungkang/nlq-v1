"""
LLM Utilities
LLM 처리를 위한 유틸리티 함수들
"""

import re
import json
from typing import Dict, Any, List, Optional
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def clean_sql_response(response: str) -> str:
    """
    LLM 응답에서 SQL 쿼리를 정리하여 추출
    """
    if not response:
        return ""
    
    # 코드 블록 제거 (```sql ... ```)
    response = re.sub(r'```(?:sql)?\s*\n?(.*?)\n?```', r'\1', response, flags=re.DOTALL)
    
    # 일반적인 불필요한 텍스트 제거
    response = response.replace('여기는 요청하신 SQL 쿼리입니다:', '')
    response = response.replace('다음은 SQL 쿼리입니다:', '')
    response = response.replace('SQL:', '')
    
    # 앞뒤 공백 제거
    response = response.strip()
    
    # 마지막에 세미콜론이 없으면 추가
    if response and not response.rstrip().endswith(';'):
        response = response.rstrip() + ';'
    
    return response


def format_conversation_context(context_blocks: List[Dict[str, Any]], limit: int = 5) -> str:
    """
    대화 컨텍스트를 LLM이 이해하기 쉬운 형태로 포맷팅
    
    Args:
        context_blocks: 대화 기록 리스트
        limit: 포함할 최대 대화 수
        
    Returns:
        str: 포맷팅된 대화 컨텍스트
    """
    if not context_blocks:
        return ""
    
    # 최근 대화만 선택
    recent_blocks = context_blocks[-limit:] if len(context_blocks) > limit else context_blocks
    
    context_parts = []
    for i, block in enumerate(recent_blocks, 1):
        user_request = block.get('user_request', '')
        assistant_response = block.get('assistant_response', '')
        
        context_parts.append(f"[{i}] 사용자: {user_request}")
        context_parts.append(f"[{i}] AI: {assistant_response}")
    
    return "\n".join(context_parts)


def extract_sql_patterns(context_blocks: List[Dict[str, Any]]) -> List[str]:
    """
    이전 대화에서 사용된 SQL 패턴들을 추출
    """
    patterns = []
    
    for block in context_blocks:
        generated_query = block.get('generated_query', '')
        if generated_query and generated_query.strip():
            patterns.append(generated_query.strip())
    
    return patterns[-3:]  # 최근 3개만 반환


def normalize_conversation_context(raw_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    원시 대화 블록을 정규화하여 일관된 형태로 변환
    """
    normalized = []
    
    for block in raw_blocks:
        normalized_block = {
            'user_request': str(block.get('user_request', '')).strip(),
            'assistant_response': str(block.get('assistant_response', '')).strip(),
            'generated_query': str(block.get('generated_query', '')).strip() if block.get('generated_query') else None,
            'block_type': block.get('block_type', 'unknown'),
            'timestamp': block.get('timestamp')
        }
        
        # 모든 블록 포함 (빈 상태도 구조 유지)
        normalized.append(normalized_block)
    
    return normalized


def extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    LLM 응답에서 JSON 추출
    """
    try:
        # 직접 JSON 파싱 시도
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # JSON 패턴 찾기
    json_patterns = [
        r'\{.*\}',
        r'\[.*\]'
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def sanitize_error_message(error_msg: str) -> str:
    """
    에러 메시지에서 민감한 정보 제거
    """
    # API 키 패턴 제거
    sanitized = re.sub(r'api[_-]?key["\']?\s*:\s*["\'][^"\']+["\']', 'api_key: [REDACTED]', error_msg, flags=re.IGNORECASE)
    
    # 토큰 패턴 제거
    sanitized = re.sub(r'token["\']?\s*:\s*["\'][^"\']+["\']', 'token: [REDACTED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized


def extract_latest_result_rows(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    가장 최근 ContextBlock에서 RAW 결과 행을 추출(비변형)
    """
    try:
        for blk in reversed(blocks):
            execution_result = blk.get('execution_result')
            if execution_result:
                data = execution_result.get('data')
                if isinstance(data, list) and data:
                    return data
        return []
    except Exception:
        return []


def pack_rows_as_json(rows: List[Dict[str, Any]], max_rows: int = 200, max_chars: int = 60000) -> str:
    """
    RAW 행 리스트를 JSON 문자열로 직렬화(무손실, 크기 제한만 적용)
    """
    if not rows:
        return "[]"
    
    n = min(len(rows), max_rows)
    while n >= 1:
        chunk = rows[:n]
        s = json.dumps(chunk, ensure_ascii=False, separators=(',', ':'))
        if len(s) <= max_chars:
            return s
        # 크기 초과 시 행 수를 줄여 재시도(70% 비율로 감소)
        new_n = int(n * 0.7)
        n = new_n if new_n < n else n - 1
    
    # 최소 1행도 초과하면 빈 배열 반환
    return "[]"


def format_analysis_context(context_messages: List[Dict[str, Any]], limit: int = 5) -> str:
    """
    데이터 분석용으로 컨텍스트를 풍부하게 요약 (결과 샘플 포함)
    """
    if not context_messages:
        return "[이전 대화 없음]"

    lines = []
    # 최근 메시지만 고려
    msgs = context_messages[-limit:]
    
    for msg in msgs:
        role = "사용자" if msg.get('role') == 'user' else 'AI'
        timestamp = msg.get('timestamp', '')[:19] if msg.get('timestamp') else ''
        content = msg.get('content', '') or ''
        
        if len(content) > 200:
            content = content[:200] + '...'

        # 기본 라인
        base = f"[{timestamp}] {role}: {content}"
        lines.append(base)
        
        # 쿼리 결과가 있으면 샘플 데이터 추가
        if role == 'AI' and 'query_result' in msg:
            query_result = msg.get('query_result', {})
            data = query_result.get('data', [])
            if data and isinstance(data, list):
                # 첫 2행, 최대 3컬럼만 표시
                sample_rows = data[:2]
                if sample_rows:
                    headers = list(sample_rows[0].keys())[:3]
                    lines.append(f"  연관 데이터 샘플: {headers}")
                    for row in sample_rows:
                        row_data = {k: row.get(k) for k in headers}
                        lines.append(f"    {row_data}")
    
    return "\n".join(lines)


def extract_questions_from_text(text: str) -> List[str]:
    """
    텍스트에서 질문들을 추출하는 헬퍼 함수
    """
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
            question = match.strip()
            # 중복 제거 및 최소 길이 검증
            if question and len(question) > 5 and question not in questions:
                questions.append(question)
    
    # 최대 10개 질문만 반환
    return questions[:10]