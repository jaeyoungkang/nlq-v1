# 📊 Phase 2: 분석 블록(Analysis Block) 구현 계획

## 🎯 개요
Phase 1에서 구현한 통합 테이블 구조를 기반으로, "분석 블록" 개념을 도입하여 더욱 체계적이고 확장 가능한 데이터 모델로 발전시킵니다.

---

## 🔍 현재 상태 (Phase 1 완료)

### 구현된 기능
- ✅ 통합된 conversations 테이블 (JOIN 없는 구조)
- ✅ `save_complete_interaction()` 메서드
- ✅ `get_conversation_with_context()` 메서드
- ✅ 단일 테이블 기반 성능 향상

### 한계점
- 질문-답변이 하나의 문자열로 저장됨 (`Q: ... \nA: ...`)
- 블록 타입 구분이 명확하지 않음
- 참조 관계 관리가 제한적
- 확장성 부족 (시각화, 대시보드 등 새로운 기능 추가 어려움)

---

## 🚀 Phase 2 목표

### 핵심 개념: "분석 블록(Analysis Block)"
하나의 완전한 분석 사이클을 나타내는 독립적인 데이터 단위

### 주요 목표
1. **구조화된 데이터 모델**: 블록 타입별 명확한 구분
2. **유연한 확장성**: 새로운 블록 타입 쉽게 추가
3. **향상된 참조 관계**: 블록 간 관계 체계적 관리
4. **메타데이터 강화**: 분석 과정 추적 및 모니터링

---

## 📐 설계

### 1. AnalysisBlock 데이터 모델

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class BlockType(Enum):
    """분석 블록 타입"""
    QUERY = "QUERY"              # SQL 쿼리 실행
    ANALYSIS = "ANALYSIS"        # 데이터 분석
    VISUALIZATION = "VISUALIZATION"  # 시각화
    METADATA = "METADATA"        # 메타데이터 조회
    COMPOUND = "COMPOUND"        # 복합 분석

@dataclass
class AnalysisBlock:
    """분석 블록: 하나의 완전한 분석 사이클"""
    # 기본 식별자
    block_id: str
    user_id: str
    timestamp: datetime
    block_type: BlockType
    
    # 사용자 요청
    user_request: Dict[str, Any]  # {"content": "...", "timestamp": "...", "context": {...}}
    
    # AI 응답
    assistant_response: Dict[str, Any]  # {"sql": "...", "analysis": "...", "message": "...", "confidence": 0.95}
    
    # 실행 결과 (있는 경우)
    execution_result: Optional[Dict[str, Any]] = None  # {"data": [...], "row_count": N, "execution_time_ms": 123}
    
    # 메타데이터
    metadata: Dict[str, Any] = None  # {"model_version": "...", "tokens_used": N, "cache_hit": false}
    
    # 참조 관계
    referenced_blocks: List[str] = None  # 이 블록이 참조한 이전 블록들
    child_blocks: List[str] = None       # 이 블록에서 파생된 하위 블록들
    
    # 상태 관리
    status: str = "completed"  # "pending", "processing", "completed", "failed"
    error_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'block_id': self.block_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'block_type': self.block_type.value,
            'user_request': self.user_request,
            'assistant_response': self.assistant_response,
            'execution_result': self.execution_result,
            'metadata': self.metadata,
            'referenced_blocks': self.referenced_blocks or [],
            'child_blocks': self.child_blocks or [],
            'status': self.status,
            'error_info': self.error_info
        }
```

### 2. 개선된 서비스 레이어

```python
class AnalysisBlockService:
    """분석 블록 관리 서비스"""
    
    def __init__(self, project_id: str, location: str = "asia-northeast3"):
        self.project_id = project_id
        self.location = location
        self.client = bigquery.Client(project=project_id, location=location)
    
    def create_analysis_block(self, 
                            user_id: str,
                            user_question: str,
                            block_type: BlockType,
                            referenced_blocks: List[str] = None) -> AnalysisBlock:
        """새로운 분석 블록 생성"""
        block = AnalysisBlock(
            block_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            block_type=block_type,
            user_request={
                "content": user_question,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "chat_interface"
            },
            assistant_response={},
            referenced_blocks=referenced_blocks,
            status="pending"
        )
        return block
    
    def process_query_block(self, block: AnalysisBlock, sql: str, query_result: dict) -> AnalysisBlock:
        """쿼리 블록 처리"""
        block.assistant_response = {
            "sql": sql,
            "message": f"쿼리 실행 완료: {query_result.get('row_count', 0)}개 행 반환",
            "query_explanation": self._explain_sql(sql)
        }
        
        block.execution_result = {
            "data": query_result.get('data', []),
            "row_count": query_result.get('row_count', 0),
            "execution_time_ms": query_result.get('execution_time_ms'),
            "bytes_processed": query_result.get('bytes_processed')
        }
        
        block.metadata = {
            "query_complexity": self._calculate_query_complexity(sql),
            "tables_accessed": self._extract_tables(sql),
            "estimated_cost": query_result.get('estimated_cost')
        }
        
        block.status = "completed"
        return block
    
    def process_analysis_block(self, block: AnalysisBlock, analysis_result: dict) -> AnalysisBlock:
        """분석 블록 처리"""
        block.assistant_response = {
            "analysis": analysis_result.get('analysis'),
            "insights": analysis_result.get('insights', []),
            "recommendations": analysis_result.get('recommendations', []),
            "confidence_score": analysis_result.get('confidence', 0.8)
        }
        
        block.metadata = {
            "analysis_type": analysis_result.get('type', 'general'),
            "data_points_analyzed": analysis_result.get('data_points'),
            "patterns_found": len(analysis_result.get('patterns', []))
        }
        
        block.status = "completed"
        return block
    
    def save_block(self, block: AnalysisBlock) -> Dict[str, Any]:
        """분석 블록 저장"""
        try:
            dataset_name = os.getenv('CONVERSATION_DATASET', 'v1')
            table_ref = self.client.dataset(dataset_name).table('analysis_blocks')
            
            # 테이블이 없으면 생성
            self._ensure_analysis_blocks_table(dataset_name)
            
            # 데이터 저장
            errors = self.client.insert_rows_json(table_ref, [block.to_dict()])
            
            if errors:
                logger.error(f"블록 저장 실패: {errors}")
                return {"success": False, "error": errors[0]}
            
            logger.info(f"✅ 분석 블록 저장 완료: {block.block_id} ({block.block_type.value})")
            return {"success": True, "block_id": block.block_id}
            
        except Exception as e:
            logger.error(f"블록 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_blocks_by_type(self, user_id: str, block_type: BlockType, limit: int = 10) -> List[AnalysisBlock]:
        """특정 타입의 블록 조회"""
        query = f"""
        SELECT *
        FROM `{{project}}.{{dataset}}.analysis_blocks`
        WHERE user_id = @user_id
          AND block_type = @block_type
        ORDER BY timestamp DESC
        LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('user_id', 'STRING', user_id),
                bigquery.ScalarQueryParameter('block_type', 'STRING', block_type.value),
                bigquery.ScalarQueryParameter('limit', 'INT64', limit)
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        return [self._row_to_block(row) for row in results]
    
    def get_block_lineage(self, block_id: str) -> Dict[str, Any]:
        """블록의 계보 추적 (참조된 블록들과 파생된 블록들)"""
        query = f"""
        WITH RECURSIVE block_tree AS (
            -- 시작 블록
            SELECT block_id, referenced_blocks, child_blocks, 0 as level
            FROM `{{project}}.{{dataset}}.analysis_blocks`
            WHERE block_id = @block_id
            
            UNION ALL
            
            -- 참조된 블록들 (상위)
            SELECT b.block_id, b.referenced_blocks, b.child_blocks, bt.level - 1
            FROM `{{project}}.{{dataset}}.analysis_blocks` b
            JOIN block_tree bt ON b.block_id IN UNNEST(bt.referenced_blocks)
            WHERE bt.level > -3  -- 최대 3단계 상위까지
            
            UNION ALL
            
            -- 파생된 블록들 (하위)
            SELECT b.block_id, b.referenced_blocks, b.child_blocks, bt.level + 1
            FROM `{{project}}.{{dataset}}.analysis_blocks` b
            JOIN block_tree bt ON b.block_id IN UNNEST(bt.child_blocks)
            WHERE bt.level < 3  -- 최대 3단계 하위까지
        )
        SELECT * FROM block_tree
        ORDER BY level, block_id
        """
        
        # 블록 계보 구성 및 반환
        # ...
```

### 3. API 레이어 개선

```python
from fastapi import APIRouter, Depends
from typing import List, Optional

router = APIRouter()

@router.post("/api/v2/analysis", response_model=AnalysisBlockResponse)
async def create_analysis_block(
    request: AnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    block_service: AnalysisBlockService = Depends(get_block_service)
):
    """새로운 분석 블록 생성 및 처리"""
    
    # 1. 블록 타입 결정
    block_type = determine_block_type(request.message)
    
    # 2. 분석 블록 생성
    block = block_service.create_analysis_block(
        user_id=user_id,
        user_question=request.message,
        block_type=block_type,
        referenced_blocks=request.referenced_blocks
    )
    
    # 3. 블록 타입별 처리
    if block_type == BlockType.QUERY:
        # SQL 생성 및 실행
        sql = await generate_sql(request.message, request.context)
        result = await execute_query(sql)
        block = block_service.process_query_block(block, sql, result)
        
    elif block_type == BlockType.ANALYSIS:
        # 데이터 분석 수행
        analysis = await perform_analysis(request.message, request.data)
        block = block_service.process_analysis_block(block, analysis)
        
    elif block_type == BlockType.VISUALIZATION:
        # 시각화 생성
        viz = await create_visualization(request.data, request.viz_type)
        block = block_service.process_visualization_block(block, viz)
    
    # 4. 블록 저장
    save_result = block_service.save_block(block)
    
    if not save_result['success']:
        raise HTTPException(status_code=500, detail=save_result['error'])
    
    return AnalysisBlockResponse(
        block_id=block.block_id,
        block_type=block.block_type.value,
        status=block.status,
        response=block.assistant_response,
        execution_result=block.execution_result
    )

@router.get("/api/v2/blocks/{block_id}/lineage")
async def get_block_lineage(
    block_id: str,
    user_id: str = Depends(get_current_user_id),
    block_service: AnalysisBlockService = Depends(get_block_service)
):
    """블록의 계보 조회"""
    lineage = block_service.get_block_lineage(block_id)
    return {
        "block_id": block_id,
        "lineage": lineage,
        "visualization_url": f"/visualize/lineage/{block_id}"
    }

@router.get("/api/v2/blocks/search")
async def search_blocks(
    query: str,
    block_types: Optional[List[BlockType]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user_id: str = Depends(get_current_user_id),
    block_service: AnalysisBlockService = Depends(get_block_service)
):
    """블록 검색"""
    results = block_service.search_blocks(
        user_id=user_id,
        query=query,
        block_types=block_types,
        date_range=(date_from, date_to)
    )
    return {
        "query": query,
        "count": len(results),
        "blocks": results
    }
```

---

## 📊 데이터베이스 스키마

### analysis_blocks 테이블

```sql
CREATE TABLE analysis_blocks (
  -- 기본 식별자
  block_id STRING NOT NULL,
  user_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  
  -- 블록 타입 및 상태
  block_type STRING NOT NULL,  -- 'QUERY', 'ANALYSIS', 'VISUALIZATION', 'METADATA', 'COMPOUND'
  status STRING NOT NULL,       -- 'pending', 'processing', 'completed', 'failed'
  
  -- 구조화된 데이터
  user_request JSON NOT NULL,      -- 사용자 요청 정보
  assistant_response JSON NOT NULL, -- AI 응답 정보
  execution_result JSON,            -- 실행 결과 (선택적)
  metadata JSON,                    -- 메타데이터
  
  -- 참조 관계
  referenced_blocks ARRAY<STRING>,  -- 참조한 블록들
  child_blocks ARRAY<STRING>,       -- 파생된 블록들
  
  -- 에러 정보
  error_info JSON,
  
  -- 인덱싱을 위한 추가 컬럼
  created_date DATE,  -- 파티셔닝용
  search_text STRING, -- 전문 검색용
  
) PARTITION BY created_date
CLUSTER BY user_id, block_type;

-- 인덱스 생성
CREATE INDEX idx_block_type ON analysis_blocks(block_type);
CREATE INDEX idx_user_timestamp ON analysis_blocks(user_id, timestamp DESC);
CREATE INDEX idx_referenced_blocks ON analysis_blocks(referenced_blocks);
```

---

## 🔄 마이그레이션 전략

### 1단계: 기존 데이터 변환
```python
def migrate_to_analysis_blocks():
    """기존 conversations 데이터를 analysis_blocks로 변환"""
    
    migration_query = """
    INSERT INTO `{project}.{dataset}.analysis_blocks`
    SELECT 
        message_id as block_id,
        user_id,
        timestamp,
        CASE 
            WHEN generated_sql IS NOT NULL THEN 'QUERY'
            ELSE 'ANALYSIS'
        END as block_type,
        'completed' as status,
        
        -- user_request 구성
        TO_JSON_STRING(STRUCT(
            SPLIT(message, '\\nA: ')[OFFSET(0)] as content,
            timestamp as timestamp,
            'migrated' as source
        )) as user_request,
        
        -- assistant_response 구성
        TO_JSON_STRING(STRUCT(
            generated_sql as sql,
            SPLIT(message, '\\nA: ')[SAFE_OFFSET(1)] as message
        )) as assistant_response,
        
        -- execution_result 구성
        IF(result_data IS NOT NULL,
            TO_JSON_STRING(STRUCT(
                result_data as data,
                result_row_count as row_count
            )),
            NULL
        ) as execution_result,
        
        -- metadata
        TO_JSON_STRING(STRUCT(
            'migration' as source,
            CURRENT_TIMESTAMP() as migrated_at
        )) as metadata,
        
        context_message_ids as referenced_blocks,
        [] as child_blocks,
        NULL as error_info,
        DATE(timestamp) as created_date,
        message as search_text
        
    FROM `{project}.{dataset}.conversations`
    WHERE message_type = 'complete'
    """
```

### 2단계: 듀얼 라이팅
- 신규 요청은 analysis_blocks에 저장
- 하위 호환성을 위해 conversations에도 동시 저장 (임시)

### 3단계: 점진적 전환
- 읽기 작업을 analysis_blocks로 전환
- 모니터링 및 성능 검증
- conversations 테이블 deprecation

---

## 📈 예상 효과

### 성능 개선
- **쿼리 성능**: 블록 타입별 클러스터링으로 20-30% 향상
- **검색 속도**: 전문 검색 인덱스로 50% 향상
- **분석 효율**: 블록 간 관계 추적으로 컨텍스트 구성 최적화

### 기능 확장
- **새로운 블록 타입**: VISUALIZATION, DASHBOARD 등 쉽게 추가
- **고급 분석**: 블록 계보 추적, 패턴 분석
- **협업 기능**: 블록 공유, 템플릿화

### 개발 생산성
- **명확한 구조**: 블록 타입별 명확한 처리 로직
- **재사용성**: 블록 단위 재사용 및 조합
- **테스트 용이성**: 블록 단위 독립적 테스트

---

## 📅 구현 일정

### Week 1: 데이터 모델 및 서비스 레이어
- Day 1-2: AnalysisBlock 클래스 및 BlockType enum 구현
- Day 3-4: AnalysisBlockService 구현
- Day 5: 단위 테스트 작성

### Week 2: API 및 마이그레이션
- Day 1-2: API v2 엔드포인트 구현
- Day 3-4: 마이그레이션 스크립트 작성 및 테스트
- Day 5: 듀얼 라이팅 구현

### Week 3: 통합 및 최적화
- Day 1-2: 프론트엔드 연동
- Day 3-4: 성능 최적화 및 모니터링
- Day 5: 문서화 및 배포

---

## 🚨 리스크 및 대응

### 기술적 리스크
- **데이터 마이그레이션 실패**: 롤백 계획 수립, 단계별 검증
- **성능 저하**: 블록 크기 제한, 캐싱 전략 수립
- **복잡도 증가**: 명확한 문서화, 팀 교육

### 운영 리스크
- **하위 호환성**: API 버전 관리, 점진적 전환
- **사용자 혼란**: UI/UX 가이드, 사용자 교육

---

## 🎯 성공 지표

### 정량적 지표
- 평균 응답 시간 20% 단축
- 블록 재사용률 30% 이상
- 에러율 10% 감소

### 정성적 지표
- 개발자 만족도 향상
- 새 기능 개발 속도 향상
- 시스템 이해도 증가

---

## 🎉 결론

Phase 2 "분석 블록" 구현을 통해:

1. **체계적인 데이터 모델**: 명확한 블록 타입과 구조
2. **확장 가능한 아키텍처**: 새로운 기능 쉽게 추가
3. **향상된 분석 능력**: 블록 간 관계 및 계보 추적
4. **개선된 개발 경험**: 명확한 구조와 재사용성

이를 통해 단순한 Q&A 시스템을 넘어 **진정한 데이터 분석 플랫폼**으로 진화할 수 있습니다! 🚀