# Backend Development Guidelines

> 이 문서는 nlq-v1 백엔드 개발을 위한 아키텍처 가이드라인입니다.  
> Claude Code가 코드 작성 시 반드시 준수해야 할 규칙과 패턴을 정의합니다.  
> **✅ 2025-09-03 Firestore 화이트리스트 단순화 완료** - 이메일 기반 단순 구조 달성

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
│ (Data Access)   │  ↓ Firestore 쿼리, 데이터 변환
├─────────────────┤
│    Database     │  Firestore (데이터 저장소)
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

### 4. Repository 패턴 (Firestore 기반)
```python
from core.repositories.firestore_base import FirestoreRepository

class FeatureRepository(FirestoreRepository):
    def __init__(self, project_id: Optional[str] = None):
        super().__init__(collection_name="feature_data", project_id=project_id)
    
    # BaseRepository 인터페이스 구현 (필수)
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock 저장 - 구현 필요"""
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자 대화 조회 - 구현 필요"""
    
    def check_user_whitelist(self, email: str, user_id: str = None) -> Dict[str, Any]:
        """화이트리스트 검증 - AuthRepository에서만 구현 (이메일 기반 단순화)"""
        
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """화이트리스트에 사용자 추가 - AuthRepository에서만 구현 (이메일 기반)"""
```

### 5. ContextBlock 중심 설계 원칙
- ContextBlock = 완전한 대화 컨텍스트 단위 (대화 정보 + 쿼리 결과)
- 모든 대화/컨텍스트 데이터는 `ContextBlock` 모델 기반
- 공유 도메인 모델은 `core/models/`에 위치
- 테이블 스키마는 ContextBlock과 완전 매칭
- **용도별 최적화**: 대화 정보는 항상 포함, 쿼리 결과는 필요시만 사용

## 디렉토리 구조 (Firestore 기반)

```
backend/
├── core/
│   ├── models/
│   │   ├── __init__.py          # ContextBlock, BlockType exports
│   │   └── context.py           # 공유 도메인 모델 (변경없음)
│   └── repositories/
│       ├── base.py              # 추상 BaseRepository (ABC)
│       └── firestore_base.py    # Firestore 구현체 + FirestoreClient
├── features/
│   ├── authentication/
│   │   ├── repositories.py     # whitelist 컬렉션 관리 (AuthRepository) - 이메일 기반 단순화
│   │   ├── services.py         # 인증 비즈니스 로직 - 이메일 기반
│   │   └── routes.py          # 인증 API 엔드포인트
│   ├── chat/
│   │   ├── repositories.py     # users/{email}/conversations 관리 (ChatRepository) - 이메일 키
│   │   ├── services.py         # 대화 오케스트레이션
│   │   └── routes.py          # 대화 API 엔드포인트
│   ├── query_processing/
│   │   └── services.py         # BigQuery 직접 연결 (Repository 제거)
│   ├── data_analysis/
│   │   └── services.py         # ChatRepository 사용 (Repository 제거)
│   ├── input_classification/
│   │   └── services.py         # LLM 서비스만 사용
│   └── llm/
│       ├── repositories.py     # LLM API 연결 (유지)
│       └── services.py         # LLM 비즈니스 로직
├── firebase/                   # Firebase 설정 파일들 (신규)
│   ├── firebase.json          # Firebase 프로젝트 설정
│   ├── firestore.rules        # Firestore 보안 규칙
│   ├── firestore.indexes.json # 복합 인덱스 설정
│   └── README.md             # Firebase 설정 가이드
├── utils/                       # 범용 유틸리티 (변경없음)
├── add_user_to_whitelist.py    # 화이트리스트 관리 스크립트 (단순화)
└── app.py                      # 단순화된 의존성 주입
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

#### Repository (Data Access) 계층 (Firestore)
```python
from core.repositories.firestore_base import FirestoreRepository
from core.models import ContextBlock
from google.cloud import firestore

class ChatRepository(FirestoreRepository):
    """대화 관련 데이터 접근 계층 (Firestore 구현) - 이메일 키 기반"""
    
    def __init__(self, project_id=None):
        # users 컬렉션 사용 (conversations 서브컬렉션 포함)
        super().__init__(collection_name="users", project_id=project_id)
    
    def save_context_block(self, context_block: ContextBlock) -> Dict[str, Any]:
        """ContextBlock을 users/{email}/conversations에 저장 (이메일 키)"""
        try:
            # 사용자별 conversations 서브컬렉션에 저장 (user_id = 이메일)
            user_ref = self.client.collection("users").document(context_block.user_id)
            conversations_ref = user_ref.collection("conversations")
            
            # block_id를 문서 ID로 사용
            conversations_ref.document(context_block.block_id).set(context_block.to_dict())
            
            return {"success": True, "block_id": context_block.block_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """사용자의 대화 기록 조회 (user_id = 이메일 주소)"""
        try:
            # user_id는 이메일 주소
            user_ref = self.client.collection("users").document(user_id)
            conversations_ref = user_ref.collection("conversations")
            
            # timestamp 기준 내림차순으로 정렬
            query = conversations_ref.order_by("timestamp", 
                                             direction=firestore.Query.DESCENDING).limit(limit)
            
            # ContextBlock 객체로 변환하여 반환
            docs = query.stream()
            context_blocks = [self._doc_to_context_block(doc) for doc in docs]
            
            return {"success": True, "context_blocks": context_blocks}
        except Exception as e:
            return {"success": False, "error": str(e), "context_blocks": []}

class AuthRepository(FirestoreRepository):
    """인증 관련 데이터 접근 계층 (Firestore 구현) - 이메일 기반 단순화"""
    
    def __init__(self, project_id=None):
        # whitelist 컬렉션 사용
        super().__init__(collection_name="whitelist", project_id=project_id)
    
    def check_user_whitelist(self, email: str, user_id: str = None) -> Dict[str, Any]:
        """whitelist 컬렉션에서 이메일 기반 권한 확인 (단순화)"""
        try:
            # 이메일을 문서 ID로 직접 조회
            whitelist_ref = self.client.collection("whitelist").document(email)
            whitelist_doc = whitelist_ref.get()
            
            if not whitelist_doc.exists:
                return {"success": True, "allowed": False, "reason": "not_whitelisted"}
            
            # 화이트리스트에 존재하면 무조건 허용
            return {"success": True, "allowed": True, "message": "접근 허용"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def save_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """화이트리스트에 사용자 이메일 추가 (단순화된 구조)"""
        try:
            email = user_data.get('email')
            if not email:
                return {"success": False, "error": "이메일이 필요합니다"}
            
            # 단순화된 화이트리스트 데이터 구조
            whitelist_data = {
                'email': email,
                'created_at': datetime.now(timezone.utc)
            }
            
            # 화이트리스트에 이메일을 문서 ID로 저장
            whitelist_ref = self.client.collection("whitelist").document(email)
            whitelist_ref.set(whitelist_data, merge=True)
            
            return {"success": True, "message": "사용자가 화이트리스트에 추가되었습니다"}
        except Exception as e:
            return {"success": False, "error": str(e)}
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
6. **ContextBlock 설계 원칙 준수**: 모든 대화 컨텍스트는 ContextBlock 유틸리티 함수 활용
7. **구조적 일관성**: 불필요한 분기 없이 빈 상태도 일관된 구조 유지

### 금지 사항
- ❌ 계층 건너뛰기 (Controller에서 Repository 직접 호출)
- ❌ 직접 딕셔너리 응답 반환 (ErrorResponse/SuccessResponse 사용 필수)
- ❌ 기본 logging 모듈 사용 (utils.logging_utils 사용 필수)
- ❌ 현재 불필요한 추가 기능 구현
- ❌ **ContextBlock execution_result 직접 접근**
- ❌ **ContextBlock 부분 활용** (완전한 컨텍스트 단위로만 처리)
- ❌ **불필요한 분기 로직 생성**

### 코드 작성 체크리스트
- [ ] 적절한 계층에 코드 배치
- [ ] 의존성 주입 패턴 적용
- [ ] 표준 에러 처리 및 로깅 사용
- [ ] API 계약 준수 (표준 응답 형식)
- [ ] 인증 데코레이터 적용
- [ ] ContextBlock 모델과 테이블 스키마 매칭
- [ ] **ContextBlock 설계 원칙 준수**:
  - [ ] ContextBlock 유틸리티 함수 (`context_blocks_to_llm_format` 등) 활용
  - [ ] `execution_result` 직접 접근 없음
  - [ ] 용도별 최적화 (대화 정보 vs 전체 컨텍스트) 적용
  - [ ] 불필요한 분기 로직 생성 방지 (빈 상태도 일관된 구조 유지)

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

    # 설계 원칙: 용도별 최적화된 메서드 제공
    def to_conversation_format(self) -> Dict:
        """대화 정보만 (분류/SQL생성용 - 토큰 절약)"""
        
    def to_full_context_format(self) -> Dict:
        """전체 컨텍스트 (데이터 분석용)"""
        
```

### ContextBlock 유틸리티 함수 활용 (필수)
```python
# 올바른 패턴 - 모델의 유틸리티 함수 활용
from core.models.context import (
    context_blocks_to_llm_format,      # 대화 히스토리용 (토큰 절약)
    context_blocks_to_complete_format, # 완전한 맥락 보존 (JSON 직렬화)
    create_analysis_context,           # 분석용 전체 컨텍스트
)

# 용도별 최적화 (개선된 패턴)
if purpose == "classification":
    messages = context_blocks_to_llm_format(context_blocks)     # 대화 히스토리만
elif purpose == "data_analysis":
    complete_data = context_blocks_to_complete_format(context_blocks)  # 완전한 맥락
    analysis_context = create_analysis_context(context_blocks)  # 메타정보 포함

# ✅ 올바른 패턴 (분기 없이 일관된 구조)
# 빈 상태라도 구조적 일관성 유지
llm_context.append(block.to_assistant_llm_format())  # 분기 없이 항상 포함
query_row_count = (block.execution_result or {}).get("row_count", 0)  # 간결한 패턴

# ❌ 금지된 패턴
for block in context_blocks:
    data = block.execution_result['data']  # 직접 접근 금지
    if block.assistant_response:  # 불필요한 분기 생성 금지
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
execution_result: JSON NULLABLE  # {"data": [...], "row_count": N}
status: STRING REQUIRED
```

### ContextBlock 활용 패턴 (Feature-Driven)
```python
# features/input_classification/services.py
def classify(self, message: str, context_blocks: List[ContextBlock]):
    request = ClassificationRequest(
        user_input=message,
        context_blocks=context_blocks  # ✅ 완전한 ContextBlock 전달
    )
    return self.llm_service.classify_input(request)

# features/llm/services.py  
def classify_input(self, request: ClassificationRequest):
    # ✅ ContextBlock 유틸리티 함수 활용
    context_formatted = self._format_context_blocks_for_prompt(request.context_blocks)
    # ❌ 금지: block.execution_result['data'] 직접 접근
```

## LLM 아키텍처 및 구현 패턴

### LLM 서비스 구조 (features/llm/)
Feature-Driven 아키텍처를 따르는 LLM 전담 모듈:

```
features/llm/
├── models.py          # LLM 요청/응답 모델 
├── services.py        # LLM 비즈니스 로직 (핵심)
├── utils.py          # SQL 정리, 응답 파싱 등 LLM 전용 유틸
└── repositories/     # LLM 인프라 (core/llm/repositories/에 위치)
```

### 중앙화된 LLMService 패턴
```python
# features/llm/services.py
class LLMService:
    def __init__(self, repository: BaseLLMRepository, cache_loader=None):
        self.repository = repository  # Anthropic Claude 연동
        self.cache_loader = cache_loader or get_metasync_cache_loader()
    
    def classify_input(self, request: ClassificationRequest) -> ClassificationResponse:
        """입력 분류 - 대화 정보만 활용 (토큰 절약)"""
        
    def generate_sql(self, request: SQLGenerationRequest) -> SQLGenerationResponse:
        """SQL 생성 - MetaSync 캐시 + 대화 컨텍스트"""
        
    def analyze_data(self, request: AnalysisRequest) -> AnalysisResponse:
        """데이터 분석 - 완전한 컨텍스트 (대화 + 쿼리 결과)"""
```

### 프롬프트 관리 시스템
JSON 기반 중앙화된 프롬프트 템플릿 (`core/prompts/`):

```python
# 프롬프트 사용 패턴
system_prompt = prompt_manager.get_prompt(
    category='sql_generation',           # classification, sql_generation, data_analysis
    template_name='system_prompt',       # system_prompt, user_prompt
    table_id=template_vars['table_id'],  # 템플릿 변수 치환
    schema_columns=template_vars['schema_columns'],
    fallback_prompt=FallbackPrompts.sql_system(...)  # 폴백
)
```

### ContextBlock 기반 LLM 연동
LLM과 ContextBlock의 완벽한 통합:

```python
# ✅ 올바른 구현 패턴 - features/llm/services.py
def _format_context_blocks_for_prompt(self, context_blocks: List[ContextBlock]) -> str:
    """ContextBlock → 프롬프트용 텍스트 변환 (완전한 컨텍스트)"""
    # ContextBlock 유틸리티 함수 활용
    from core.models.context import context_blocks_to_llm_format
    recent_blocks = context_blocks[-5:]  # 최근 5개만
    llm_messages = context_blocks_to_llm_format(recent_blocks)
    
    # AI 응답에 실행결과 메타정보 추가 (분기 없이 일관된 구조)
    for msg in llm_messages:
        if msg["role"] == "assistant":  # 필수적인 역할 구분만 유지
            # 메타정보는 항상 포함 (빈 상태라도 구조 유지)
            meta_info = []
            generated_query = (msg.get("metadata") or {}).get("generated_query")
            query_row_count = msg.get("query_row_count", 0)
            
            # 조건부 추가가 아닌 일관된 처리
            meta_info.append(f"SQL: {generated_query or 'None'}")
            meta_info.append(f"결과: {query_row_count}개 행")

def _prepare_analysis_context_json(self, context_blocks: List[ContextBlock]) -> str:
    """데이터 분석용 완전한 컨텍스트 준비"""
    # ContextBlock 모델의 전용 유틸리티 함수 활용
    from core.models.context import create_analysis_context
    context_data = create_analysis_context(context_blocks)
    return json.dumps(context_data, ensure_ascii=False, indent=2)
```

### MetaSync 통합 LLM 패턴
SQL 생성 시 MetaSync 캐시 데이터 자동 활용:

```python
def _prepare_sql_template_variables(self, request, context_blocks_formatted):
    """MetaSync 스키마/Few-Shot 데이터를 템플릿 변수로 준비"""
    template_vars = {
        'table_id': request.default_table,
        'context_blocks': context_blocks_formatted,
        'question': request.user_question,
        'schema_columns': '',      # MetaSync에서 로드
        'few_shot_examples': ''    # MetaSync에서 로드
    }
    
    # MetaSync 데이터 자동 주입 (의존성 체크 필수)
    if self.cache_loader:  # 필수 의존성 체크 - 제거 불가
        schema_info = self.cache_loader.get_schema_info()
        examples = self.cache_loader.get_few_shot_examples()
        # 템플릿 변수에 자동 매핑
    
    return template_vars
```

### 용도별 최적화된 LLM 호출
ContextBlock 설계 의도에 따른 용도별 최적화:

```python
# 1. 입력 분류/SQL 생성: 대화 정보만 (토큰 절약)
def classify_input(self, request: ClassificationRequest):
    context_formatted = self._format_context_blocks_for_prompt(request.context_blocks)
    # 대화 히스토리만 포함, 쿼리 결과는 제외
    
def generate_sql(self, request: SQLGenerationRequest):
    context_formatted = self._format_context_blocks_for_prompt(request.context_blocks)
    # 대화 + 쿼리 메타정보만, 실제 데이터는 제외
    
# 2. 데이터 분석: 완전한 컨텍스트 (대화 + 쿼리 결과)
def analyze_data(self, request: AnalysisRequest):
    context_json = self._prepare_analysis_context_json(request.context_blocks)
    # 대화 정보 + 쿼리 결과 데이터 완전한 맥락으로 포함
    
    user_prompt = prompt_manager.get_prompt(
        category='data_analysis',
        template_name='user_prompt',
        context_json=context_json,  # ContextBlock 완전한 단위로 전달
        question=request.user_question
    )
```

### Feature Services의 LLM 연동 패턴
각 기능별 서비스에서 LLMService 활용:

```python
# features/input_classification/services.py
class InputClassificationService:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
    
    def classify(self, message: str, context_blocks: List[ContextBlock]):
        request = ClassificationRequest(
            user_input=message,
            context_blocks=context_blocks  # ContextBlock 그대로 전달
        )
        return self.llm_service.classify_input(request)

# features/query_processing/services.py  
class QueryProcessingService:
    def __init__(self, llm_service: LLMService, repository):
        self.llm_service = llm_service
        
    def _process_sql_query(self, request: QueryRequest, context_blocks: List[ContextBlock]):
        sql_request = SQLGenerationRequest(
            user_question=request.query,
            context_blocks=context_blocks  # ContextBlock 그대로 전달
        )
        sql_response = self.llm_service.generate_sql(sql_request)
```

### LLM 의존성 주입 패턴
app.py에서 중앙화된 의존성 주입:

```python
# app.py
# 1. LLM Repository 초기화
llm_repository = AnthropicRepository(api_key=anthropic_api_key)

# 2. MetaSync 캐시 로더 초기화  
cache_loader = get_metasync_cache_loader()

# 3. LLM Service 생성 (의존성 주입)
app.llm_service = LLMService(llm_repository, cache_loader)

# 4. Feature Services에 LLM Service 주입
app.input_classification_service = InputClassificationService(app.llm_service)
app.query_processing_service = QueryProcessingService(app.llm_service, query_repo)
app.data_analysis_service = DataAnalysisService(app.llm_service, analysis_repo)
```

## Firebase 설정 및 배포

### Firebase 설정 파일 구조 (`firebase/` 디렉토리)

```
firebase/
├── firebase.json          # Firebase 프로젝트 설정
├── firestore.rules        # Firestore 보안 규칙
├── firestore.indexes.json # 복합 인덱스 설정  
└── README.md             # Firebase 설정 가이드
```

### Firestore 보안 규칙 (`firebase/firestore.rules`)

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // 화이트리스트 컬렉션 - 이메일 기반 단순화
    match /whitelist/{email} {
      // 사용자는 자신의 이메일로 된 화이트리스트만 읽기 가능
      allow read: if request.auth != null && request.auth.token.email == email;
      // 관리자는 모든 화이트리스트 관리 가능
      allow read, write: if request.auth != null && 
                          request.auth.token.admin == true;
    }
    
    // 사용자 컬렉션 - 이메일 기반 접근 제어
    match /users/{email} {
      allow read, write: if request.auth != null && request.auth.token.email == email;
      
      match /conversations/{conversationId} {
        allow read, write: if request.auth != null && request.auth.token.email == email;
      }
    }
  }
}
```

### Firebase 배포 명령어

```bash
# 보안 규칙 배포
cd backend/firebase
firebase deploy --only firestore:rules --project nlq-ex

# 인덱스 배포
firebase deploy --only firestore:indexes --project nlq-ex

# 전체 Firestore 설정 배포
firebase deploy --only firestore --project nlq-ex
```

## 화이트리스트 관리

### 단순화된 화이트리스트 구조

```
whitelist/user@example.com/
├── email: "user@example.com"
└── created_at: timestamp
```

### 화이트리스트 사용자 추가 (`add_user_to_whitelist.py`)

```bash
# 사용법 (단순화)
python3 add_user_to_whitelist.py <email>

# 예시
python3 add_user_to_whitelist.py user@example.com
```

#### 스크립트 핵심 로직
```python
def add_user_to_whitelist(email: str):
    """이메일을 Firestore 화이트리스트에 추가 (단순화된 구조)"""
    # 단순화된 화이트리스트 데이터 구조
    whitelist_data = {
        'email': email,
        'created_at': datetime.now(timezone.utc)
    }
    
    # 이메일을 문서 ID로 저장
    whitelist_ref = client.collection("whitelist").document(email)
    whitelist_ref.set(whitelist_data, merge=True)
```

### 화이트리스트 인증 플로우 (이메일 기반 + users 문서 자동 생성)

1. **사용자 Google 로그인** 
2. **이메일 추출** (Google OAuth 토큰에서)
3. **JWT 토큰 생성** (user_id = 이메일, Google user_id 별도 보관)
4. **whitelist/{email} 문서 조회**
5. **문서 존재 여부로 허용/차단 결정**
6. **users/{email} 문서 자동 생성/업데이트** ← 추가됨
7. **conversations 서브컬렉션 접근 준비**

### 화이트리스트 관리 명령어

```bash
# 사용자 추가
python3 add_user_to_whitelist.py user@example.com

# 사용자 제거 (Firebase 콘솔 또는 CLI)
gcloud firestore documents delete projects/nlq-ex/databases/(default)/documents/whitelist/user@example.com

# 모든 화이트리스트 사용자 조회
gcloud firestore documents list projects/nlq-ex/databases/(default)/documents/whitelist
```

## 최신 업데이트 내역

### ✅ 2025-09-03 Firestore 이메일 기반 통합 완료

#### 주요 변경사항
1. **화이트리스트 구조 단순화**
   - 복잡한 Google user_id 기반 → 이메일 기반 구조 + 자동 users 문서 생성
   - status, last_login 등 불필요한 필드 제거
   - 문서 존재 = 허용, 미존재 = 차단 방식

2. **Users 컬렉션 이메일 키 변경**
   - `users/{google_user_id}/` → `users/{email}/` 구조 변경 + 인증 시 자동 문서 생성
   - ChatRepository 이메일 기반 조회 및 저장
   - ContextBlock의 user_id가 이메일 주소

3. **인증 시스템 완전 개편**
   - **TokenHandler**: JWT 토큰 내 user_id를 이메일로 변경, Google user_id 별도 필드
   - **AuthService**: 이메일 기반 세션 관리 + users 문서 자동 생성 추가
   - **AuthRepository**: `ensure_user_document()` 메서드 신규 추가
   - `authenticate_google_user()` 이메일 중심 검증
   - `logout_user()`, `link_session_to_user()` 이메일 기반

4. **Firestore 보안 규칙 통합**
   - whitelist, users 모두 `request.auth.token.email` 기반
   - 일관된 이메일 접근 제어 정책
   - 대화 데이터 생성 시 이메일 검증

5. **Firebase 설정 구조화**
   - `firebase/` 디렉토리 생성
   - Firebase 설정 파일들 체계적 관리
   - 보안 규칙 및 인덱스 이메일 기반으로 통합

6. **화이트리스트 스크립트 단순화**
   - `add_user_to_whitelist.py <email>` 단순 사용법
   - UUID 자동 생성 로직 제거
   - 이메일만으로 바로 추가 가능

#### 개선 효과
- **시스템 일관성 극대화**: 모든 컬렉션이 이메일 키 기반
- **보안 규칙 단순화**: `request.auth.token.email` 하나로 통합
- **관리 효율성 극대화**: 이메일 하나로 모든 관리
- **직관적 데이터 구조**: 이메일 = 문서 ID (whitelist, users 공통)
- **Google OAuth 완벽 호환**: JWT 토큰 user_id = 이메일, Google user_id 별도 보관
- **자동 사용자 관리**: 인증 성공 시 users 컬렉션에 문서 자동 생성/업데이트

#### 관련 문서
- `FIRESTORE_EMAIL_MIGRATION.md` - 상세 작업 보고서
- `firebase/README.md` - Firebase 설정 가이드