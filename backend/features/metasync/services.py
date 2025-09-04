"""
MetaSync Service - 메타데이터 캐시 비즈니스 로직
Cloud Function MetaSync의 핵심 로직을 백엔드 Feature로 이전
LLMService 재사용으로 중복 코드 제거
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from features.metasync.models import (
    MetadataCache, SchemaInfo, EventsTableInfo, FewShotExample,
    CacheUpdateRequest, CacheStatus
)
from features.metasync.repositories import MetaSyncRepository
from features.llm.services import LLMService
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class MetaSyncService:
    """
    MetaSync 메타데이터 캐시 비즈니스 로직
    Cloud Function MetaSync의 모든 기능을 Feature Service로 구현
    """
    
    def __init__(self, llm_service: LLMService, 
                 repository: Optional[MetaSyncRepository] = None,
                 default_table: str = "nlq-ex.test_dataset.events_20210131"):
        """
        MetaSync Service 초기화
        
        Args:
            llm_service: LLM 서비스 (Few-Shot 예시 및 인사이트 생성용)
            repository: MetaSync Repository
            default_table: 기본 대상 테이블
        """
        self.llm_service = llm_service
        self.repository = repository or MetaSyncRepository()
        self.default_table = default_table
    
    def get_cache_data(self) -> Dict[str, Any]:
        """
        현재 캐시 데이터 조회
        기존 MetaSyncCacheLoader 호환 인터페이스
        
        Returns:
            캐시 데이터 딕셔너리
        """
        try:
            return self.repository.get_cache_data()
        except Exception as e:
            logger.error(f"Failed to get cache data: {str(e)}")
            return self.repository._get_empty_cache_structure()
    
    def get_cache_status(self) -> CacheStatus:
        """
        캐시 상태 조회
        
        Returns:
            CacheStatus 객체
        """
        try:
            return self.repository.get_cache_status()
        except Exception as e:
            logger.error(f"Failed to get cache status: {str(e)}")
            return CacheStatus(
                exists=False,
                last_updated=None,
                size_bytes=None,
                table_count=0,
                example_count=0,
                is_valid=False,
                error_message=str(e)
            )
    
    def update_cache(self, request: Optional[CacheUpdateRequest] = None) -> Dict[str, Any]:
        """
        메타데이터 캐시 업데이트 (Cloud Function 메인 로직)
        
        Args:
            request: 캐시 업데이트 요청 (옵션)
            
        Returns:
            업데이트 결과
        """
        request = request or CacheUpdateRequest()
        
        try:
            logger.info("Starting metadata cache update")
            
            # 1. 캐시 만료 확인 (force_refresh가 아닌 경우)
            if not request.force_refresh and self.repository.is_cache_available():
                logger.info("Cache is still valid, skipping update")
                return {
                    "success": True,
                    "message": "Cache is still valid",
                    "cache_updated": False,
                    "status": self.get_cache_status().to_dict()
                }
            
            # 2. BigQuery 스키마 조회
            logger.info(f"Fetching schema for {self.default_table}")
            schema_info = self.repository.fetch_bigquery_schema(self.default_table)
            
            # 3. Events 테이블 목록 수집
            logger.info("Fetching events tables list")
            events_tables = self.repository.fetch_events_tables_list(self.default_table)
            
            # 4. 샘플 데이터 조회 (Few-Shot 예시 생성용)
            sample_data = []
            if request.include_examples:
                logger.info("Fetching sample data for examples")
                sample_data = self.repository.fetch_sample_data(self.default_table, limit=100)
            
            # 5. Few-Shot 예시 생성 (LLM 활용)
            examples = []
            if request.include_examples:
                logger.info("Generating Few-Shot examples using LLM")
                examples = self._generate_few_shot_examples(schema_info, events_tables, sample_data)
            
            # 6. 스키마 인사이트 생성 (LLM 활용)
            schema_insights = {}
            if request.include_insights:
                logger.info("Generating schema insights using LLM")
                schema_insights = self._generate_schema_insights(schema_info, sample_data)
            
            # 7. Events 테이블 추상화
            events_table_info = self._abstract_events_tables(events_tables)
            
            # 8. MetadataCache 객체 생성
            metadata_cache = MetadataCache(
                generated_at=datetime.now(timezone.utc).isoformat(),
                generation_method="llm_enhanced",
                schema=schema_info.to_dict(),
                examples=[example.to_dict() for example in examples],
                events_tables=events_table_info.to_dict() if events_table_info else {},
                schema_insights=schema_insights
            )
            
            # 9. 캐시 저장
            logger.info("Saving metadata cache")
            save_result = self.repository.save_cache(metadata_cache, create_snapshot=True)
            
            if save_result.get("success"):
                logger.info("Metadata cache updated successfully")
                return {
                    "success": True,
                    "message": "Cache updated successfully",
                    "cache_updated": True,
                    "generated_at": metadata_cache.generated_at,
                    "stats": metadata_cache.get_cache_stats(),
                    "save_result": save_result
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save cache",
                    "details": save_result
                }
                
        except Exception as e:
            logger.error(f"Failed to update cache: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "cache_updated": False
            }
    
    def _generate_few_shot_examples(self, schema_info: SchemaInfo, 
                                  events_tables: List[str],
                                  sample_data: List[Dict[str, Any]]) -> List[FewShotExample]:
        """
        LLM을 활용한 Few-Shot 예시 생성
        Cloud Function의 generate_examples_with_llm() 로직 이전
        
        Args:
            schema_info: 테이블 스키마 정보
            events_tables: Events 테이블 목록
            sample_data: 샘플 데이터
            
        Returns:
            생성된 Few-Shot 예시 목록
        """
        try:
            # 예시에 사용할 테이블 결정
            example_table = self.default_table
            if events_tables and len(events_tables) > 0:
                example_table = events_tables[-1]
            
            # LLM 프롬프트 준비
            system_prompt = """BigQuery 테이블의 스키마를 보고 3개의 간단한 SQL 예시를 JSON으로 생성하세요.

규칙:
- event_timestamp는 TIMESTAMP_MICROS()로 변환
- 모든 쿼리에 LIMIT 100 포함
- 기본 조회, 집계, 시간 분석 위주

JSON 형식:
[{"description": "질문", "sql_query": "SELECT ..."}]"""

            # 스키마 정보 포맷팅
            schema_text = "테이블 스키마:\n"
            for col in schema_info.columns:
                schema_text += f"- {col['name']} ({col['type']}): {col.get('description', '')}\n"

            user_prompt = f"""{schema_text}

3개 예시 생성: 전체 조회, 날짜별 집계, 이벤트 타입별 분석"""

            # LLM 호출 (LLMService의 직접 호출 메서드 활용)
            response = self.llm_service.call_llm_direct(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1000,
                temperature=0.3
            )
            
            if response:
                try:
                    # JSON 응답 파싱
                    examples_data = json.loads(response)
                    if isinstance(examples_data, list) and len(examples_data) > 0:
                        examples = []
                        for example_data in examples_data:
                            example = FewShotExample(
                                description=example_data.get('description', ''),
                                sql_query=example_data.get('sql_query', ''),
                                result_summary=example_data.get('result_summary')
                            )
                            examples.append(example)
                        
                        logger.info(f"Generated {len(examples)} examples using LLM")
                        return examples
                    else:
                        logger.warning("LLM response is not a valid list")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
            
            # LLM 실패 시 폴백 예시
            logger.info("Falling back to hardcoded examples")
            return self._generate_fallback_examples(example_table, events_tables)
            
        except Exception as e:
            logger.error(f"Error in _generate_few_shot_examples: {e}")
            return self._generate_fallback_examples(example_table, events_tables)
    
    def _generate_fallback_examples(self, example_table: str, 
                                  events_tables: List[str]) -> List[FewShotExample]:
        """
        LLM 실패 시 폴백 예시 생성
        Cloud Function의 _generate_fallback_examples() 로직 이전
        """
        examples = [
            FewShotExample(
                description="총 이벤트 수는 얼마인가요?",
                sql_query=f"SELECT COUNT(*) as total_events FROM `{example_table}` LIMIT 100;"
            ),
            FewShotExample(
                description="날짜별 이벤트 수를 보여주세요",
                sql_query=f"SELECT DATE(TIMESTAMP_MICROS(event_timestamp)) as date, COUNT(*) as event_count FROM `{example_table}` GROUP BY 1 ORDER BY 1 DESC LIMIT 10;"
            ),
            FewShotExample(
                description="이벤트 타입별 분포를 알려주세요",
                sql_query=f"SELECT event_name, COUNT(*) as count FROM `{example_table}` GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
            ),
            FewShotExample(
                description="시간대별 이벤트 패턴을 분석해주세요",
                sql_query=f"SELECT EXTRACT(HOUR FROM TIMESTAMP_MICROS(event_timestamp)) as hour, COUNT(*) as event_count FROM `{example_table}` GROUP BY 1 ORDER BY 1 LIMIT 100;"
            )
        ]
        
        # 다중 테이블이 있으면 UNION 예시 추가
        if events_tables and len(events_tables) >= 2:
            examples.append(FewShotExample(
                description="여러 날짜의 데이터를 통합 분석해주세요",
                sql_query=f"SELECT event_name, COUNT(*) as count FROM `{events_tables[0]}` UNION ALL SELECT event_name, COUNT(*) as count FROM `{events_tables[1]}` LIMIT 100;"
            ))
        
        logger.info(f"Generated {len(examples)} fallback examples")
        return examples
    
    def _generate_schema_insights(self, schema_info: SchemaInfo,
                                sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        LLM을 활용한 스키마 인사이트 생성
        Cloud Function의 generate_schema_insights_with_llm() 로직 이전
        """
        try:
            # 스키마 정보 포맷팅
            schema_text = "테이블 스키마:\n"
            for col in schema_info.columns:
                schema_text += f"- {col['name']} ({col['type']}): {col.get('description', '')}\n"
            
            # 샘플 데이터 포맷팅 (처음 5개)
            sample_text = "샘플 데이터 (처음 5개 행):\n"
            if sample_data:
                for i, row in enumerate(sample_data[:5]):
                    sample_text += f"행 {i+1}: {json.dumps(row, ensure_ascii=False, default=str)}\n"
            
            system_prompt = """테이블 스키마를 보고 간단한 분석 정보를 JSON으로 생성하세요.

JSON 형식:
{
  "purpose": "이벤트 로그 테이블",
  "key_columns": ["event_name", "user_id", "event_timestamp"],
  "analysis_tips": ["시간대별 분석 가능", "사용자별 행동 추적"]
}"""

            user_prompt = f"""{schema_text}

간단한 분석 정보 생성"""

            # LLM 호출 (LLMService의 직접 호출 메서드 활용)
            response = self.llm_service.call_llm_direct(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=500,
                temperature=0.3
            )
            
            if response:
                try:
                    # JSON 응답 파싱
                    insights = json.loads(response)
                    if isinstance(insights, dict):
                        logger.info("Generated schema insights using LLM")
                        return insights
                    else:
                        logger.warning("LLM response is not a valid dict")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM insights response as JSON: {e}")
            
            # LLM 실패 시 빈 인사이트 반환
            logger.info("No schema insights generated")
            return {}
            
        except Exception as e:
            logger.error(f"Error in _generate_schema_insights: {e}")
            return {}
    
    def _abstract_events_tables(self, events_tables: List[str]) -> Optional[EventsTableInfo]:
        """
        Events 테이블 목록을 추상화 (토큰 절약용)
        Cloud Function의 abstract_events_tables() 로직 이전
        """
        if not events_tables:
            return None
        
        try:
            # 날짜 범위 추출
            dates = []
            for table in events_tables:
                # nlq-ex.test_dataset.events_20201101 -> 20201101
                if 'events_' in table:
                    date_part = table.split('events_')[-1]
                    if len(date_part) == 8 and date_part.isdigit():
                        dates.append(date_part)
            
            if not dates:
                return EventsTableInfo(
                    count=len(events_tables),
                    pattern="events_YYYYMMDD",
                    date_range={},
                    example_tables=events_tables[:2] if len(events_tables) >= 2 else events_tables
                )
            
            dates.sort()
            start_date = dates[0]  # 20201101
            end_date = dates[-1]   # 20210131
            
            # 포맷팅된 날짜로 변환
            def format_date(date_str: str) -> str:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            events_info = EventsTableInfo(
                count=len(events_tables),
                pattern="nlq-ex.test_dataset.events_YYYYMMDD",
                date_range={
                    "start": format_date(start_date),
                    "end": format_date(end_date)
                },
                example_tables=[
                    events_tables[0],   # 첫 번째
                    events_tables[-1]   # 마지막
                ]
            )
            
            logger.info(f"Abstracted {len(events_tables)} events tables")
            return events_info
            
        except Exception as e:
            logger.error(f"Failed to abstract events tables: {str(e)}")
            return EventsTableInfo(
                count=len(events_tables),
                pattern="events_YYYYMMDD",
                date_range={},
                example_tables=events_tables[:2] if len(events_tables) >= 2 else events_tables
            )
    
    def refresh_cache(self) -> Dict[str, Any]:
        """
        캐시 강제 새로고침 (메모리 캐시 초기화 + 재로드)
        
        Returns:
            새로고침 결과
        """
        try:
            success = self.repository.refresh_cache()
            
            if success:
                return {
                    "success": True,
                    "message": "Cache refreshed successfully",
                    "status": self.get_cache_status().to_dict()
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to refresh cache"
                }
                
        except Exception as e:
            logger.error(f"Failed to refresh cache: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_snapshots(self) -> Dict[str, Any]:
        """
        캐시 스냅샷 목록 조회
        
        Returns:
            스냅샷 목록 및 정보
        """
        try:
            snapshots = self.repository.list_cache_snapshots()
            
            return {
                "success": True,
                "snapshots": snapshots,
                "count": len(snapshots),
                "message": f"Found {len(snapshots)} cache snapshots"
            }
            
        except Exception as e:
            logger.error(f"Failed to list snapshots: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "snapshots": [],
                "count": 0
            }