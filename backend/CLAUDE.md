# Backend Development Guidelines

> 이 문서는 nlq-v1 백엔드 개발을 위한 아키텍처 가이드라인입니다.  
> Claude Code가 코드 작성 시 반드시 준수해야 할 규칙과 패턴을 정의합니다.

## 아키텍처 원칙

### 1. 기능 주도 모듈화 (Feature-Driven Architecture)
- 각 기능은 독립된 모듈로 구성: authentication, chat, data_analysis, query_processing 등
- 기능별 수직 분할로 높은 응집도와 낮은 결합도 달성

### 2. 계층형 아키텍처 (Layered Architecture)
```
┌─────────────────┐
│   Controller    │  routes.py (API 엔드포인트, 요청/응답 처리)
│    (Routes)     │  ↓ HTTP 요청/응답, 인증, 검증
├─────────────────┤
│    Service      │  services.py (비즈니스 로직, 도메인 규칙)
│ (Business Logic)│  ↓ 도메인 객체, 규칙 적용
├─────────────────┤
│   Repository    │  repositories.py (데이터 접근, CRUD)
│ (Data Access)   │  ↓ SQL 쿼리, 데이터 변환
├─────────────────┤
│    Database     │  BigQuery (데이터 저장소)
└─────────────────┘
```

#### 계층 간 의존성 규칙:
- **상위 계층 → 하위 계층**: 허용 (Controller는 Service 호출 가능)
- **하위 계층 → 상위 계층**: 금지 (Repository는 Service 호출 불가)
- **계층 건너뛰기**: 금지 (Controller가 Repository 직접 호출 불가)

### 3. 의존성 주입 패턴
```python
class FeatureService:
    def __init__(self, llm_client, repository: Optional[FeatureRepository] = None):
        self.llm_client = llm_client
        self.repository = repository or FeatureRepository()
```

### 4. Repository 패턴
```python
from core.repositories.base import BaseRepository

class FeatureRepository(BaseRepository):
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        super().__init__(table_name="feature_data", dataset_name="v1", 
                         project_id=project_id, location=location)
```

### 5. ContextBlock 기반 데이터 모델
- 모든 대화/컨텍스트 데이터는 `ContextBlock` 모델 기반
- 공유 도메인 모델은 `core/models/`에 위치
- 테이블 스키마는 ContextBlock과 완전 매칭

## 디렉토리 구조

```
backend/
├── core/
│   ├── models/
│   │   ├── __init__.py          # ContextBlock, BlockType exports
│   │   └── context.py           # 공유 도메인 모델
│   └── repositories/
│       └── base.py              # 공통 BaseRepository
├── features/feature_name/       # 기능별 독립 모듈
│   ├── models.py               # 기능별 전용 모델
│   ├── services.py             # 비즈니스 로직
│   ├── repositories.py         # 데이터 접근
│   └── routes.py              # API 엔드포인트 (선택적)
└── app.py                      # 의존성 주입 및 초기화
```

## API 계약 (API Contract)

### 표준 응답 형식
모든 API는 일관된 응답 구조를 사용해야 합니다:

```python
# 성공 응답
{
    "success": true,
    "data": { /* 응답 데이터 */ },
    "message": "처리 완료"
}

# 에러 응답  
{
    "success": false,
    "error": "오류 메시지",
    "error_type": "validation_error|auth_error|internal_error",
    "details": { /* 추가 정보 */ }
}
```

### 응답 클래스 사용
```python
from utils.error_utils import ErrorResponse, SuccessResponse

# 성공
return jsonify(SuccessResponse.success(data, "처리 완료"))

# 에러
return jsonify(ErrorResponse.validation_error("잘못된 요청")), 400
```

### HTTP 상태 코드 표준
- `200`: 성공
- `400`: 잘못된 요청 (validation_error)
- `401`: 인증 필요 (auth_error) 
- `404`: 리소스 없음 (not_found_error)
- `500`: 서버 오류 (internal_error)

### 요청/응답 검증
```python
@feature_bp.route('/endpoint', methods=['POST'])
@require_auth
def feature_endpoint():
    # 요청 검증
    if not request.json or 'required_field' not in request.json:
        return jsonify(ErrorResponse.validation_error("필수 필드 누락")), 400
    
    try:
        result = service.process(request.json)
        return jsonify(SuccessResponse.success(result))
    except Exception as e:
        logger.error(f"처리 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error("처리 실패")), 500
```

## 블루프린트 구조화

### 라우트 분류 기준
- **기능별 라우트** (`features/*/routes.py`): 각 기능의 API 엔드포인트

### 블루프린트 등록
```python
# app.py - 직접 등록 방식
from features.authentication.routes import auth_bp
from features.chat.routes import chat_bp
from features.system.routes import system_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)  
app.register_blueprint(system_bp)
```

### URL 구조 표준
```
/api/auth/*              # 인증 관련 (features/authentication)
/api/chat-stream         # 대화 처리 (features/chat)
/api/conversations/*     # 대화 관리 (features/chat)
/api/system/*            # 시스템 관리 (features/system)
```

## 개발 규칙

### 코드 작성 원칙
- **최소 구현**: 현재 불필요한 코드 작성 금지
- **단일 책임**: 클래스/메서드당 하나의 책임  
- **명시적 의존성**: 생성자 주입 사용

### 계층별 구현 규칙

#### Controller (Routes) 계층
```python
@feature_bp.route('/endpoint', methods=['POST'])
@require_auth  # 인증 필수
def feature_endpoint():
    # 1. 요청 검증
    if not request.json:
        return jsonify(ErrorResponse.validation_error("JSON required")), 400
    
    # 2. 서비스 의존성 주입
    repository = getattr(current_app, 'feature_repository')
    service = FeatureService(current_app.llm_client, repository)
    
    # 3. 비즈니스 로직 호출 (Service 계층)
    try:
        result = service.process(request.json)
        return jsonify(SuccessResponse.success(result))
    except Exception as e:
        logger.error(f"처리 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error("처리 실패")), 500
```

#### Service (Business Logic) 계층
```python
class FeatureService:
    def __init__(self, llm_client, repository):
        self.llm_client = llm_client
        self.repository = repository
    
    def process(self, data):
        # 1. 비즈니스 규칙 검증
        if not self._validate_business_rules(data):
            raise ValidationError("비즈니스 규칙 위반")
        
        # 2. 도메인 로직 처리
        result = self._business_logic(data)
        
        # 3. 데이터 저장 (Repository 계층 호출)
        save_result = self.repository.save_data(result)
        if not save_result.get("success"):
            logger.warning(f"저장 실패: {save_result.get('error')}")
        
        return result
```

#### Repository (Data Access) 계층
```python
from core.repositories.base import BaseRepository, bigquery
from core.models import ContextBlock

class FeatureRepository(BaseRepository):
    def __init__(self, project_id=None, location="asia-northeast3"):
        super().__init__(table_name="feature_data", dataset_name="v1", 
                         project_id=project_id, location=location)
    
    def ensure_table_exists(self):
        """ContextBlock 기반 테이블 생성"""
        # ContextBlock과 호환되는 스키마 정의
        schema = [
            bigquery.SchemaField("block_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            # ... 기타 ContextBlock 필드들
        ]
        # 테이블 생성 로직
    
    def save_context_block(self, context_block: ContextBlock):
        return self.save(context_block.to_dict())
```

### 에러 처리 및 로깅
```python
from utils.logging_utils import get_logger
from utils.error_utils import ErrorResponse

logger = get_logger(__name__)

def process_data(self, data):
    try:
        result = self._business_logic(data)
        
        # 저장
        save_result = self.repository.save(result)
        if not save_result.get("success"):
            logger.warning(f"저장 실패: {save_result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"처리 오류: {str(e)}")
        raise
```

### 테스트 패턴
```python
def test_service_with_mock():
    mock_repo = Mock()
    mock_repo.save.return_value = {"success": True}
    
    service = FeatureService(llm_client, mock_repo)
    result = service.process(test_data)
    
    assert result.success is True
    mock_repo.save.assert_called_once()
```

## 새 기능 추가 가이드

### 1. 모듈 생성
```bash
mkdir features/new_feature
touch features/new_feature/{__init__.py,models.py,services.py,repositories.py}
```

### 2. 의존성 주입 설정
```python
# app.py
app.new_feature_repository = NewFeatureRepository(project_id, location)

# 사용
repository = getattr(current_app, 'new_feature_repository', None)
service = NewFeatureService(llm_client, repository)
```

### 3. 라우트 추가 (복잡한 API가 필요한 경우)
```python
# features/new_feature/routes.py
new_feature_bp = Blueprint('new_feature', __name__, url_prefix='/api/new-feature')

@new_feature_bp.route('/process', methods=['POST'])
@require_auth
def process():
    repository = getattr(current_app, 'new_feature_repository')
    service = NewFeatureService(current_app.llm_client, repository)
    return jsonify(SuccessResponse.success(service.process(request.json)))
```

## Claude Code 구현 지침

### 필수 준수 사항
1. **계층 분리 엄격히 준수**: Controller → Service → Repository 순서로만 호출
2. **의존성 주입 필수**: 모든 서비스는 생성자에서 의존성 받기
3. **에러 처리 표준화**: `ErrorResponse`/`SuccessResponse` 클래스만 사용
4. **로깅 표준화**: `utils.logging_utils.get_logger()` 함수만 사용
5. **인증 필수**: 모든 API 엔드포인트에 `@require_auth` 데코레이터 적용

### 금지 사항
- ❌ 계층 건너뛰기 (Controller에서 Repository 직접 호출)
- ❌ 직접 딕셔너리 응답 반환 (ErrorResponse/SuccessResponse 사용 필수)
- ❌ 기본 logging 모듈 사용 (utils.logging_utils 사용 필수)
- ❌ 현재 불필요한 추가 기능 구현

### 코드 작성 체크리스트
- [ ] 적절한 계층에 코드 배치
- [ ] 의존성 주입 패턴 적용
- [ ] 표준 에러 처리 및 로깅 사용
- [ ] API 계약 준수 (표준 응답 형식)
- [ ] 인증 데코레이터 적용
- [ ] ContextBlock 모델과 테이블 스키마 매칭

## 데이터 모델 구조

### ContextBlock 중심 설계
```python
# core/models/context.py
@dataclass
class ContextBlock:
    block_id: str              # 고유 식별자
    user_id: str               # 사용자 ID  
    timestamp: datetime        # 생성 시간
    block_type: BlockType      # QUERY, ANALYSIS, METADATA
    user_request: str          # 사용자 요청
    assistant_response: str    # AI 응답 (기본값 "")
    generated_query: Optional[str] # 생성된 쿼리 (별도 필드)
    execution_result: Optional[Dict] # 실행 결과 (기본값 None)
    status: str               # pending, processing, completed, failed
```

### 모델 분류
- **공유 모델** (`core/models/`): ContextBlock, BlockType
- **기능별 모델** (`features/*/models.py`): QueryRequest, AnalysisRequest 등

### 테이블 스키마 표준
모든 ContextBlock 관련 테이블은 다음 기본 필드를 포함:
```sql
block_id: STRING REQUIRED
user_id: STRING REQUIRED
timestamp: TIMESTAMP REQUIRED  
block_type: STRING REQUIRED
user_request: STRING REQUIRED
assistant_response: STRING NULLABLE
generated_query: STRING NULLABLE
execution_result: JSON NULLABLE
status: STRING REQUIRED
```