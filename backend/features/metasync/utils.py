"""
MetaSync 유틸리티 함수
메타데이터 처리 및 변환을 위한 헬퍼 함수들
"""

from typing import List, Dict, Any, Optional
import re
from datetime import datetime
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def extract_date_from_table_name(table_name: str) -> Optional[str]:
    """
    테이블 이름에서 날짜 추출
    
    Args:
        table_name: 테이블 이름 (예: "nlq-ex.test_dataset.events_20210131")
        
    Returns:
        추출된 날짜 (YYYYMMDD 형식) 또는 None
    """
    try:
        # events_YYYYMMDD 패턴에서 날짜 추출
        match = re.search(r'events_(\d{8})', table_name)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        logger.warning(f"Failed to extract date from table name {table_name}: {e}")
        return None


def format_date_string(date_str: str) -> str:
    """
    날짜 문자열 포맷팅 (YYYYMMDD -> YYYY-MM-DD)
    
    Args:
        date_str: 날짜 문자열 (YYYYMMDD 형식)
        
    Returns:
        포맷된 날짜 문자열 (YYYY-MM-DD)
    """
    try:
        if len(date_str) != 8 or not date_str.isdigit():
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return date_str


def parse_table_id_components(table_id: str) -> Dict[str, str]:
    """
    테이블 ID를 구성 요소로 분해
    
    Args:
        table_id: BigQuery 테이블 ID (project.dataset.table 형식)
        
    Returns:
        {"project": "project_id", "dataset": "dataset_id", "table": "table_name"}
    """
    try:
        parts = table_id.split('.')
        if len(parts) >= 3:
            return {
                "project": parts[0],
                "dataset": parts[1],
                "table": parts[2]
            }
        elif len(parts) == 2:
            return {
                "project": "",
                "dataset": parts[0],
                "table": parts[1]
            }
        else:
            return {
                "project": "",
                "dataset": "",
                "table": table_id
            }
    except Exception as e:
        logger.warning(f"Failed to parse table ID {table_id}: {e}")
        return {
            "project": "",
            "dataset": "",
            "table": table_id
        }


def filter_events_tables(table_names: List[str]) -> List[str]:
    """
    테이블 목록에서 events 패턴 테이블만 필터링
    
    Args:
        table_names: 테이블 이름 목록
        
    Returns:
        events 패턴 테이블 목록 (정렬됨)
    """
    try:
        events_tables = []
        
        for table_name in table_names:
            # events_ 패턴 확인
            if 'events_' in table_name:
                # 날짜 패턴 확인 (YYYYMMDD)
                date_part = extract_date_from_table_name(table_name)
                if date_part:
                    events_tables.append(table_name)
        
        # 날짜순 정렬
        events_tables.sort()
        
        logger.info(f"Filtered {len(events_tables)} events tables from {len(table_names)} total tables")
        return events_tables
        
    except Exception as e:
        logger.error(f"Failed to filter events tables: {e}")
        return []


def get_date_range_from_tables(events_tables: List[str]) -> Dict[str, str]:
    """
    Events 테이블 목록에서 날짜 범위 추출
    
    Args:
        events_tables: Events 테이블 목록
        
    Returns:
        {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    """
    try:
        if not events_tables:
            return {}
        
        dates = []
        for table in events_tables:
            date_str = extract_date_from_table_name(table)
            if date_str:
                dates.append(date_str)
        
        if not dates:
            return {}
        
        dates.sort()
        start_date = format_date_string(dates[0])
        end_date = format_date_string(dates[-1])
        
        return {
            "start": start_date,
            "end": end_date
        }
        
    except Exception as e:
        logger.error(f"Failed to get date range from tables: {e}")
        return {}


def create_table_pattern(project: str, dataset: str) -> str:
    """
    테이블 패턴 문자열 생성
    
    Args:
        project: 프로젝트 ID
        dataset: 데이터셋 ID
        
    Returns:
        테이블 패턴 문자열 (예: "nlq-ex.test_dataset.events_YYYYMMDD")
    """
    try:
        if project and dataset:
            return f"{project}.{dataset}.events_YYYYMMDD"
        elif dataset:
            return f"{dataset}.events_YYYYMMDD"
        else:
            return "events_YYYYMMDD"
    except Exception:
        return "events_YYYYMMDD"


def select_representative_tables(events_tables: List[str], 
                                max_count: int = 2) -> List[str]:
    """
    대표 테이블 선택 (첫 번째와 마지막)
    
    Args:
        events_tables: Events 테이블 목록
        max_count: 최대 반환할 테이블 수
        
    Returns:
        대표 테이블 목록
    """
    try:
        if not events_tables:
            return []
        
        if len(events_tables) <= max_count:
            return events_tables
        
        # 첫 번째와 마지막 테이블 선택
        if max_count == 2:
            return [events_tables[0], events_tables[-1]]
        
        # max_count가 2가 아닌 경우, 균등하게 분배
        step = max(1, len(events_tables) // max_count)
        selected = []
        for i in range(0, len(events_tables), step):
            selected.append(events_tables[i])
            if len(selected) >= max_count:
                break
        
        return selected
        
    except Exception as e:
        logger.error(f"Failed to select representative tables: {e}")
        return events_tables[:max_count] if events_tables else []


def validate_cache_structure(cache_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    캐시 데이터 구조 검증
    
    Args:
        cache_data: 캐시 데이터
        
    Returns:
        검증 결과 {"valid": bool, "errors": List[str]}
    """
    errors = []
    
    try:
        # 필수 필드 검증
        required_fields = ['generated_at', 'generation_method', 'schema', 'examples', 'events_tables']
        for field in required_fields:
            if field not in cache_data:
                errors.append(f"Missing required field: {field}")
        
        # 타입 검증
        if 'schema' in cache_data and not isinstance(cache_data['schema'], dict):
            errors.append("'schema' must be a dictionary")
        
        if 'examples' in cache_data and not isinstance(cache_data['examples'], list):
            errors.append("'examples' must be a list")
        
        if 'events_tables' in cache_data and not isinstance(cache_data['events_tables'], dict):
            errors.append("'events_tables' must be a dictionary")
        
        # 스키마 구조 검증
        schema = cache_data.get('schema', {})
        if schema:
            if 'table_id' not in schema:
                errors.append("schema.table_id is missing")
            if 'columns' not in schema or not isinstance(schema['columns'], list):
                errors.append("schema.columns must be a list")
        
        # 예시 구조 검증
        examples = cache_data.get('examples', [])
        for i, example in enumerate(examples):
            if not isinstance(example, dict):
                errors.append(f"examples[{i}] must be a dictionary")
                continue
            
            if 'description' not in example or 'sql_query' not in example:
                errors.append(f"examples[{i}] missing required fields")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("Cache structure validation passed")
        else:
            logger.warning(f"Cache structure validation failed: {errors}")
        
        return {
            "valid": is_valid,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Cache structure validation error: {e}")
        return {
            "valid": False,
            "errors": [str(e)]
        }


def calculate_cache_stats(cache_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    캐시 데이터 통계 계산
    
    Args:
        cache_data: 캐시 데이터
        
    Returns:
        통계 정보
    """
    try:
        schema = cache_data.get('schema', {})
        examples = cache_data.get('examples', [])
        events_tables = cache_data.get('events_tables', {})
        schema_insights = cache_data.get('schema_insights', {})
        
        stats = {
            'generated_at': cache_data.get('generated_at'),
            'generation_method': cache_data.get('generation_method'),
            'schema_tables_count': 1 if schema.get('table_id') else 0,
            'schema_columns_count': len(schema.get('columns', [])),
            'examples_count': len(examples),
            'events_tables_count': events_tables.get('count', 0),
            'events_tables_pattern': events_tables.get('pattern'),
            'has_schema_insights': bool(schema_insights),
            'cache_size_estimate': len(str(cache_data))  # 대략적인 크기
        }
        
        # 날짜 범위 정보 추가
        date_range = events_tables.get('date_range', {})
        if date_range:
            stats['date_range_start'] = date_range.get('start')
            stats['date_range_end'] = date_range.get('end')
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to calculate cache stats: {e}")
        return {
            'error': str(e)
        }


def is_cache_expired(generated_at: str, max_age_hours: int = 24) -> bool:
    """
    캐시 만료 여부 확인
    
    Args:
        generated_at: 생성 시간 (ISO format)
        max_age_hours: 최대 유효 시간 (시간)
        
    Returns:
        만료 여부
    """
    try:
        generated_time = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
        current_time = datetime.now(generated_time.tzinfo)
        age_hours = (current_time - generated_time).total_seconds() / 3600
        
        is_expired = age_hours > max_age_hours
        
        logger.info(f"Cache age: {age_hours:.2f} hours, expired: {is_expired}")
        return is_expired
        
    except Exception as e:
        logger.error(f"Failed to check cache expiration: {e}")
        return True  # 확인 실패 시 만료된 것으로 처리