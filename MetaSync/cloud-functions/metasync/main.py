import functions_framework
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from google.cloud import bigquery, storage
from google.cloud import secretmanager

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetaSyncManager:
    def __init__(self, project_id, target_table, cache_bucket):
        self.project_id = project_id
        self.target_table = target_table
        self.cache_bucket = cache_bucket
        self.bigquery_client = bigquery.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        self.bucket = self.storage_client.bucket(cache_bucket)
    
    def get_anthropic_api_key(self):
        """Secret Manager에서 API 키 가져오기"""
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.project_id}/secrets/anthropic-api-key/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"Failed to get API key from Secret Manager: {e}")
            return None
    
    def call_anthropic_api(self, system_prompt, user_prompt, max_tokens=4000, temperature=0.3):
        """Anthropic Claude API 호출"""
        api_key = self.get_anthropic_api_key()
        if not api_key:
            logger.error("Anthropic API key not available")
            return None
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result.get('content', [{}])[0].get('text', '')
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            return None
    
    def fetch_schema(self):
        """BigQuery 테이블 스키마 조회"""
        try:
            table = self.bigquery_client.get_table(self.target_table)
            schema_info = {
                "table_id": self.target_table,
                "last_updated": datetime.now().isoformat(),
                "columns": []
            }
            
            for field in table.schema:
                schema_info["columns"].append({
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or ""
                })
            
            logger.info(f"Fetched schema for {self.target_table} with {len(schema_info['columns'])} columns")
            return schema_info
            
        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}")
            raise
    
    def fetch_events_tables(self):
        """dataset에서 events_ 패턴 테이블 목록 수집"""
        try:
            # target_table에서 dataset 추출 (예: nlq-ex.test_dataset.events_20210131 -> test_dataset)
            table_parts = self.target_table.split('.')
            if len(table_parts) >= 2:
                dataset_id = table_parts[1]
                project_id = table_parts[0]
            else:
                logger.warning(f"Invalid table format: {self.target_table}")
                return []
            
            # dataset의 모든 테이블 조회
            dataset_ref = self.bigquery_client.dataset(dataset_id, project=project_id)
            tables = list(self.bigquery_client.list_tables(dataset_ref))
            
            # events_ 패턴 필터링 및 날짜순 정렬
            events_tables = []
            for table in tables:
                if table.table_id.startswith('events_'):
                    full_table_id = f"{project_id}.{dataset_id}.{table.table_id}"
                    events_tables.append(full_table_id)
            
            # 테이블명으로 정렬 (날짜 순서가 됨)
            events_tables.sort()
            
            logger.info(f"Found {len(events_tables)} events tables in dataset {dataset_id}")
            return events_tables
            
        except Exception as e:
            logger.error(f"Failed to fetch events tables: {e}")
            return []
    
    def fetch_sample_data(self, table_id, limit=100):
        """테이블의 샘플 데이터 조회"""
        try:
            query = f"""
            SELECT *
            FROM `{table_id}`
            ORDER BY RAND()
            LIMIT {limit}
            """
            
            query_job = self.bigquery_client.query(query)
            results = query_job.result()
            
            sample_data = []
            for row in results:
                sample_data.append(dict(row))
            
            logger.info(f"Fetched {len(sample_data)} sample rows from {table_id}")
            return sample_data
            
        except Exception as e:
            logger.error(f"Failed to fetch sample data from {table_id}: {e}")
            return []
    
    def generate_examples_with_llm(self, schema_info, events_tables, sample_data):
        """LLM을 활용한 동적 Few-Shot 예시 생성"""
        try:
            # 예시에 사용할 테이블 결정
            example_table = self.target_table
            if events_tables and len(events_tables) > 0:
                example_table = events_tables[-1]
            
            # 스키마 정보를 문자열로 포맷팅
            schema_text = "테이블 스키마:\n"
            for col in schema_info.get('columns', []):
                schema_text += f"- {col['name']} ({col['type']}): {col.get('description', '')}\n"
            
            # 샘플 데이터를 문자열로 포맷팅 (처음 3개만)
            sample_text = "샘플 데이터 (처음 3개 행):\n"
            if sample_data:
                for i, row in enumerate(sample_data[:3]):
                    sample_text += f"행 {i+1}: {json.dumps(row, ensure_ascii=False, default=str)}\n"
            
            # 사용 가능한 테이블 목록
            tables_text = "사용 가능한 테이블:\n"
            if events_tables:
                for table in events_tables[:5]:  # 처음 5개만
                    tables_text += f"- {table}\n"
                if len(events_tables) > 5:
                    tables_text += f"... 총 {len(events_tables)}개 테이블\n"
            else:
                tables_text += f"- {example_table}\n"
            
            system_prompt = """BigQuery 테이블의 스키마를 보고 3개의 간단한 SQL 예시를 JSON으로 생성하세요.

규칙:
- event_timestamp는 TIMESTAMP_MICROS()로 변환
- 모든 쿼리에 LIMIT 100 포함
- 기본 조회, 집계, 시간 분석 위주

JSON 형식:
[{"question": "질문", "sql": "SELECT ..."}]"""

            user_prompt = f"""{schema_text}

3개 예시 생성: 전체 조회, 날짜별 집계, 이벤트 타입별 분석"""

            # LLM 호출
            response = self.call_anthropic_api(system_prompt, user_prompt, max_tokens=1000)
            
            if response:
                try:
                    # JSON 응답 파싱
                    examples = json.loads(response)
                    if isinstance(examples, list) and len(examples) > 0:
                        logger.info(f"Generated {len(examples)} examples using LLM")
                        return examples
                    else:
                        logger.warning("LLM response is not a valid list")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
            
            # LLM 실패 시 폴백
            logger.info("Falling back to hardcoded examples")
            return self._generate_fallback_examples(example_table, events_tables)
            
        except Exception as e:
            logger.error(f"Error in generate_examples_with_llm: {e}")
            return self._generate_fallback_examples(example_table, events_tables)
    
    def _generate_fallback_examples(self, example_table, events_tables):
        """LLM 실패 시 폴백 예시 생성"""
        examples = [
            {
                "question": "총 이벤트 수는 얼마인가요?",
                "sql": f"SELECT COUNT(*) as total_events FROM `{example_table}` LIMIT 100;"
            },
            {
                "question": "날짜별 이벤트 수를 보여주세요",
                "sql": f"SELECT DATE(TIMESTAMP_MICROS(event_timestamp)) as date, COUNT(*) as event_count FROM `{example_table}` GROUP BY 1 ORDER BY 1 DESC LIMIT 10;"
            },
            {
                "question": "이벤트 타입별 분포를 알려주세요",
                "sql": f"SELECT event_name, COUNT(*) as count FROM `{example_table}` GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
            },
            {
                "question": "시간대별 이벤트 패턴을 분석해주세요",
                "sql": f"SELECT EXTRACT(HOUR FROM TIMESTAMP_MICROS(event_timestamp)) as hour, COUNT(*) as event_count FROM `{example_table}` GROUP BY 1 ORDER BY 1 LIMIT 100;"
            }
        ]
        
        # 다중 테이블이 있으면 UNION 예시 추가
        if events_tables and len(events_tables) >= 2:
            examples.append({
                "question": "여러 날짜의 데이터를 통합 분석해주세요",
                "sql": f"SELECT event_name, COUNT(*) as count FROM `{events_tables[0]}` UNION ALL SELECT event_name, COUNT(*) as count FROM `{events_tables[1]}` LIMIT 100;"
            })
        
        logger.info(f"Generated {len(examples)} fallback examples")
        return examples
    
    def generate_schema_insights_with_llm(self, schema_info, sample_data):
        """LLM을 활용한 스키마 분석 및 인사이트 생성"""
        try:
            # 스키마 정보를 문자열로 포맷팅
            schema_text = "테이블 스키마:\n"
            for col in schema_info.get('columns', []):
                schema_text += f"- {col['name']} ({col['type']}): {col.get('description', '')}\n"
            
            # 샘플 데이터를 문자열로 포맷팅 (처음 5개)
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

            # LLM 호출
            response = self.call_anthropic_api(system_prompt, user_prompt, max_tokens=500)
            
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
            logger.error(f"Error in generate_schema_insights_with_llm: {e}")
            return {}
    
    def is_cache_expired(self, max_age_hours=24):
        """캐시 만료 확인"""
        try:
            blob = self.bucket.blob("metadata_cache.json")
            if not blob.exists():
                logger.info("Cache file does not exist, needs update")
                return True
            
            blob.reload()
            age = datetime.now(blob.updated.tzinfo) - blob.updated
            expired = age > timedelta(hours=max_age_hours)
            
            if expired:
                logger.info(f"Cache expired (age: {age})")
            else:
                logger.info(f"Cache is fresh (age: {age})")
                
            return expired
            
        except Exception as e:
            logger.error(f"Failed to check cache expiration: {e}")
            return True
    
    def save_cache(self, schema_info, examples, events_tables, schema_insights=None):
        """GCS에 캐시 저장 (LLM 인사이트 포함)"""
        try:
            cache_data = {
                "generated_at": datetime.now().isoformat(),
                "generation_method": "llm_enhanced",
                "schema": schema_info,
                "examples": examples,
                "events_tables": events_tables,
                "schema_insights": schema_insights or {}
            }
            
            blob = self.bucket.blob("metadata_cache.json")
            blob.upload_from_string(
                json.dumps(cache_data, indent=2, ensure_ascii=False),
                content_type='application/json'
            )
            
            logger.info(f"Cache saved successfully with LLM insights (size: {len(json.dumps(cache_data))} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            raise
    
    def update_metadata(self):
        """메타데이터 업데이트 실행 (LLM 통합)"""
        logger.info(f"Starting LLM-enhanced metadata update for {self.target_table}")
        
        # 1. 스키마 조회
        schema_info = self.fetch_schema()
        
        # 2. events 테이블 목록 수집
        events_tables = self.fetch_events_tables()
        
        # 3. 샘플 데이터 조회 (LLM 분석용)
        sample_data = self.fetch_sample_data(self.target_table, limit=10)
        
        # 4. LLM을 활용한 Few-Shot 예시 생성
        examples = self.generate_examples_with_llm(schema_info, events_tables, sample_data)
        
        # 5. LLM을 활용한 스키마 인사이트 생성
        schema_insights = self.generate_schema_insights_with_llm(schema_info, sample_data)
        
        # 6. 캐시 저장 (인사이트 포함)
        self.save_cache(schema_info, examples, events_tables, schema_insights)
        
        logger.info("LLM-enhanced metadata update completed successfully")
        
        return {
            "updated": True,
            "method": "llm_enhanced",
            "examples_count": len(examples),
            "columns_count": len(schema_info['columns']),
            "events_tables_count": len(events_tables),
            "has_schema_insights": bool(schema_insights),
            "table_id": schema_info['table_id']
        }
    
    def check_and_update_if_needed(self):
        """필요시에만 업데이트"""
        if self.is_cache_expired():
            logger.info("Cache expired, updating...")
            return self.update_metadata()
        else:
            logger.info("Cache is fresh, no update needed")
            return {"updated": False}

@functions_framework.http
def update_metadata_cache(request):
    """HTTP Cloud Function 진입점"""
    start_time = datetime.now()
    
    try:
        # 환경변수 로드
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        target_table = os.getenv('TARGET_TABLE_ID', 'nlq-ex.test_dataset.events_20210131')
        cache_bucket = os.getenv('GCS_BUCKET', 'nlq-metadata-cache')
        
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
        
        logger.info(f"Starting MetaSync for project: {project_id}")
        logger.info(f"Target table: {target_table}")
        logger.info(f"Cache bucket: {cache_bucket}")
        
        # MetaSync 실행
        metasync = MetaSyncManager(project_id, target_table, cache_bucket)
        result = metasync.check_and_update_if_needed()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        response_data = {
            "status": "success",
            "message": "MetaSync completed successfully",
            "execution_time": execution_time,
            "timestamp": start_time.isoformat(),
            **result
        }
        
        logger.info(f"MetaSync completed in {execution_time:.2f}s - {response_data}")
        
        return response_data, 200
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        
        logger.error(f"MetaSync failed after {execution_time:.2f}s: {error_msg}", exc_info=True)
        
        error_response = {
            "status": "error",
            "message": error_msg,
            "execution_time": execution_time,
            "timestamp": start_time.isoformat()
        }
        
        return error_response, 500