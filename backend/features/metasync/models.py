"""
MetaSync 도메인 모델 정의
메타데이터 캐시 시스템의 데이터 구조와 비즈니스 규칙
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class SchemaInfo:
    """
    BigQuery 테이블 스키마 정보
    """
    table_id: str
    column_count: int
    columns: List[Dict[str, Any]]
    last_modified: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'table_id': self.table_id,
            'column_count': self.column_count,
            'columns': self.columns,
            'last_modified': self.last_modified,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchemaInfo':
        """딕셔너리에서 객체 생성"""
        return cls(
            table_id=data.get('table_id', ''),
            column_count=data.get('column_count', 0),
            columns=data.get('columns', []),
            last_modified=data.get('last_modified'),
            description=data.get('description')
        )


@dataclass
class EventsTableInfo:
    """
    Events 테이블 추상화 정보 (토큰 절약용)
    """
    count: int
    pattern: str
    date_range: Dict[str, str]
    example_tables: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'count': self.count,
            'pattern': self.pattern,
            'date_range': self.date_range,
            'example_tables': self.example_tables
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventsTableInfo':
        """딕셔너리에서 객체 생성"""
        return cls(
            count=data.get('count', 0),
            pattern=data.get('pattern', ''),
            date_range=data.get('date_range', {}),
            example_tables=data.get('example_tables', [])
        )


@dataclass
class FewShotExample:
    """
    LLM Few-Shot 학습용 예시
    """
    description: str
    sql_query: str
    result_summary: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'description': self.description,
            'sql_query': self.sql_query,
            'result_summary': self.result_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FewShotExample':
        """딕셔너리에서 객체 생성"""
        return cls(
            description=data.get('description', ''),
            sql_query=data.get('sql_query', ''),
            result_summary=data.get('result_summary')
        )


@dataclass
class MetadataCache:
    """
    MetaSync 메타데이터 캐시 전체 구조
    기존 MetaSync Cloud Function과 완전히 호환되는 구조
    """
    generated_at: str
    generation_method: str
    schema: Dict[str, Any]
    examples: List[Dict[str, Any]]
    events_tables: Dict[str, Any]
    schema_insights: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            'generated_at': self.generated_at,
            'generation_method': self.generation_method,
            'schema': self.schema,
            'examples': self.examples,
            'events_tables': self.events_tables,
            'schema_insights': self.schema_insights
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetadataCache':
        """딕셔너리에서 객체 생성"""
        return cls(
            generated_at=data.get('generated_at', ''),
            generation_method=data.get('generation_method', 'llm_enhanced'),
            schema=data.get('schema', {}),
            examples=data.get('examples', []),
            events_tables=data.get('events_tables', {}),
            schema_insights=data.get('schema_insights')
        )
    
    def get_schema_info(self, table_id: Optional[str] = None) -> Optional[SchemaInfo]:
        """특정 테이블의 스키마 정보 추출"""
        if not table_id:
            return None
            
        table_schema = self.schema.get(table_id)
        if not table_schema:
            return None
            
        return SchemaInfo.from_dict({
            'table_id': table_id,
            'column_count': len(table_schema.get('columns', [])),
            'columns': table_schema.get('columns', []),
            'last_modified': table_schema.get('last_modified'),
            'description': table_schema.get('description')
        })
    
    def get_few_shot_examples(self) -> List[FewShotExample]:
        """Few-Shot 예시 목록 반환"""
        return [FewShotExample.from_dict(example) for example in self.examples]
    
    def get_events_table_info(self) -> Optional[EventsTableInfo]:
        """Events 테이블 추상화 정보 반환"""
        if not self.events_tables:
            return None
        return EventsTableInfo.from_dict(self.events_tables)
    
    def is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """캐시 유효성 검사"""
        try:
            generated_time = datetime.fromisoformat(self.generated_at.replace('Z', '+00:00'))
            current_time = datetime.now(generated_time.tzinfo)
            age_hours = (current_time - generated_time).total_seconds() / 3600
            return age_hours <= max_age_hours
        except (ValueError, AttributeError):
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 반환"""
        return {
            'generated_at': self.generated_at,
            'generation_method': self.generation_method,
            'schema_tables': len(self.schema),
            'example_count': len(self.examples),
            'has_events_tables': bool(self.events_tables),
            'has_insights': bool(self.schema_insights),
            'cache_valid': self.is_cache_valid()
        }


@dataclass  
class CacheUpdateRequest:
    """
    캐시 업데이트 요청 모델
    """
    force_refresh: bool = False
    include_examples: bool = True
    include_insights: bool = True
    target_tables: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'force_refresh': self.force_refresh,
            'include_examples': self.include_examples,
            'include_insights': self.include_insights,
            'target_tables': self.target_tables
        }


@dataclass
class CacheStatus:
    """
    캐시 상태 정보
    """
    exists: bool
    last_updated: Optional[str]
    size_bytes: Optional[int]
    table_count: int
    example_count: int
    is_valid: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'exists': self.exists,
            'last_updated': self.last_updated,
            'size_bytes': self.size_bytes,
            'table_count': self.table_count,
            'example_count': self.example_count,
            'is_valid': self.is_valid,
            'error_message': self.error_message
        }