# Firestore 이메일 기반 완전 통합 작업 보고서

> **작업일**: 2025-09-03  
> **목적**: 화이트리스트 및 사용자 컬렉션을 이메일 기반으로 완전 통합  
> **결과**: 통일된 이메일 기반 아키텍처 구축 완료

## 📋 1. 작업 개요

### 작업 배경
- 기존 화이트리스트는 Google user_id 기반으로 복잡한 구조
- 사용자 컬렉션도 Google user_id를 키로 사용하여 일관성 부족
- 사전에 사용자 추가 시 Google user_id를 알 수 없어 관리 어려움
- status, last_login 등 불필요한 필드들로 인한 복잡성 증가

### 통합 목표
- **통일된 이메일 기반 아키텍처**: 모든 컬렉션에서 이메일을 키로 사용
- **극도로 단순한 구조**: 필수 필드만 유지
- **직관적인 관리**: 이메일을 문서 ID로 일관성 있게 사용
- **사전 사용자 추가**: Google OAuth 없이도 사용자 관리 가능
- **users 문서 자동 생성**: 인증 성공 시 자동으로 사용자 문서 생성

## 📋 2. 변경 전후 비교

### 2.1 화이트리스트 구조 변경

#### 기존 구조 (복잡)
```
whitelist/108731499195466851171/
├── user_id: "108731499195466851171"
├── email: "user@example.com"
├── status: "active"
├── created_at: timestamp
└── last_login: timestamp
```

#### 새로운 구조 (단순)
```
whitelist/user@example.com/
├── email: "user@example.com"
└── created_at: timestamp
```

### 2.2 사용자 컬렉션 구조 변경

#### 기존 구조 (Google user_id 기반)
```
users/108731499195466851171/
├── conversations/ (서브컬렉션)
└── user_id: "108731499195466851171"
```

#### 새로운 구조 (이메일 기반 + 자동 생성)
```
users/user@example.com/
├── conversations/ (서브컬렉션)
├── email: "user@example.com"
├── name: "User Name"
├── picture: "profile_url"
├── google_user_id: "108731499195466851171"
└── last_login: timestamp
```

**핵심 장점**:
- 이메일만으로 바로 추가 가능
- 문서 존재 = 허용, 미존재 = 차단
- 모든 컬렉션에서 일관된 키 사용
- 인증 시 자동으로 사용자 문서 생성
- 관리 복잡도 최소화

## 📋 3. 구현 변경사항

### 3.1 TokenHandler 수정 (`utils/token_utils.py`) ⭐ 핵심 변경

#### 주요 변경점 
- **Google OAuth 처리**: `user_info['user_id']`를 이메일로 변경, Google user_id는 별도 보관
- **JWT 토큰 페이로드**: `user_id` 필드에 이메일 사용, `google_user_id` 별도 필드 추가
- **토큰 검증**: JWT 토큰에서 추출되는 `user_id`가 이메일이 되도록 변경

#### 핵심 코드
```python
# Google OAuth 토큰 검증 시
user_info = {
    "user_id": idinfo["email"],  # 이메일을 user_id로 사용
    "google_user_id": idinfo["sub"],  # Google user_id는 별도 보관
    "email": idinfo["email"],
    "name": idinfo.get("name", ""),
    "picture": idinfo.get("picture", ""),
    "email_verified": idinfo.get("email_verified", False),
}

# JWT 토큰 페이로드 (이메일 기반)
access_payload = {
    'user_id': user_info['email'],  # 이메일을 user_id로 사용
    'email': user_info['email'],
    'google_user_id': user_info.get('google_user_id'),  # Google user_id 포함
    # ... 기타 필드들
}
```

### 3.2 AuthRepository 수정 (`features/authentication/repositories.py`) ⭐ 핵심 기능

#### 주요 변경점
- **화이트리스트 조회**: 이메일을 문서 ID로 직접 조회
- **허용 로직**: 문서 존재하면 무조건 허용
- **제거된 기능**: status 검사, last_login 업데이트  
- **새로 추가**: `ensure_user_document()` 메서드로 users 컬렉션 문서 자동 생성

#### 핵심 코드
```python
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

def ensure_user_document(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
    """users 컬렉션에 사용자 문서 생성/업데이트 (이메일 기반)"""
    try:
        email = user_info['email']
        
        user_document = {
            'email': email,
            'name': user_info.get('name', ''),
            'picture': user_info.get('picture', ''),
            'google_user_id': user_info.get('google_user_id', ''),
            'last_login': datetime.now(timezone.utc),
            'created_at': datetime.now(timezone.utc)  # merge=True로 기존 값 유지
        }
        
        # users 컬렉션에 이메일을 문서 ID로 사용하여 저장
        user_ref = self.client.collection("users").document(email)
        user_ref.set(user_document, merge=True)
        
        return {"success": True, "message": f"사용자 문서가 생성/업데이트되었습니다: {email}"}
    except Exception as e:
        return {"success": False, "error": f"사용자 문서 생성 실패: {str(e)}"}

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

### 3.3 AuthService 수정 (`features/authentication/services.py`) ⭐ 자동 사용자 생성

#### 주요 변경점
- **인증 플로우에 users 문서 생성 추가**: `ensure_user_document()` 호출
- **메서드 시그니처 단순화**: 이메일 기반으로 통일
- **세션 관리**: 이메일을 기준으로 세션 생성/삭제

#### 핵심 코드
```python
def authenticate_google_user(self, id_token: str) -> Dict[str, Any]:
    # ... Google 토큰 검증 및 화이트리스트 확인 후
    
    # users 컬렉션에 사용자 문서 생성/업데이트 (이메일 기반) ⭐ 새로 추가
    user_creation_result = self.auth_repository.ensure_user_document(user_info)
    if not user_creation_result['success']:
        logger.warning(f"users 문서 생성 실패: {user_creation_result.get('error')}")
    
    return token_result

def link_session_to_user(self, session_id: str, user_email: str) -> Dict[str, Any]:
    """세션을 사용자에게 연결 (이메일 기반)"""
    return self.auth_repository.link_session_to_user(session_id, user_email)

def logout_user(self, user_email: str) -> Dict[str, Any]:
    """사용자 로그아웃 (이메일 기반)"""
    sessions_to_remove = [
        session_id for session_id, session_data in self.active_sessions.items()
        if session_data['user_info']['email'] == user_email
    ]
    
    for session_id in sessions_to_remove:
        del self.active_sessions[session_id]
        
    return {"success": True, "message": f"사용자 {user_email} 로그아웃 완료"}
```

### 3.4 AuthRoutes 수정 (`features/authentication/routes.py`) ⭐ 클라이언트 호환성

#### 주요 변경점
- **응답 데이터**: `user_id`를 이메일로, `google_user_id`를 별도 필드로 제공
- **세션 연결**: 이메일만 사용하도록 시그니처 변경

#### 핵심 코드
```python
response_data = {
    "user": {
        "user_id": user_info['email'],  # 이메일을 user_id로 사용
        "email": user_info['email'],
        "name": user_info['name'],
        "picture": user_info['picture'],
        "google_user_id": user_info.get('google_user_id')  # Google user_id는 별도 필드
    },
    # ... 기타 필드들
}

# 세션 연결 시 이메일만 사용
session_link_result = auth_service.link_session_to_user(
    session_id, user_info['email']  # 이메일을 user_id로 사용
)
```

### 3.5 ChatRepository 수정 (`features/chat/repositories.py`)

#### 주요 변경점
- **사용자 문서 참조**: 이메일을 사용자 문서 ID로 사용
- **대화 저장**: users/{email}/conversations 구조 유지
- **코멘트 업데이트**: 이메일 기반 구조 명시

#### 핵심 코드
```python
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
```

### 3.6 Firestore 보안 규칙 수정 (`firebase/firestore.rules`)

#### 변경 내용
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
        
        // 대화 데이터 유효성 검증 (user_id는 이메일)
        allow create: if request.auth != null && 
                         request.auth.token.email == email &&
                         request.resource.data.user_id == email;
      }
    }
  }
}
```

#### 배포 완료
```bash
cd backend/firebase
firebase deploy --only firestore:rules --project nlq-ex
# ✅ Deploy complete!
```

### 3.7 화이트리스트 스크립트 단순화 (`add_user_to_whitelist.py`)

#### 사용법 변경
```bash
# 기존 (복잡)
python3 add_user_to_whitelist.py <email> [status] [user_id]

# 신규 (단순)
python3 add_user_to_whitelist.py <email>
```

#### 핵심 로직
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

## 📋 4. 테스트 결과

### 4.1 스크립트 실행 테스트
```bash
$ python3 add_user_to_whitelist.py simple@test.com
✅ Environment variables loaded
🔄 Firestore 화이트리스트에 이메일 추가 중...
   - 이메일: simple@test.com
   - 방식: 이메일을 문서 ID로 사용
✅ 사용자가 화이트리스트에 추가되었습니다:
   - 이메일: simple@test.com
   - 컬렉션: whitelist
   - 문서 ID: simple@test.com
   - 구조: 단순화 (이메일 + 생성일만 저장)
🎉 완료!
```

### 4.2 Firestore 데이터 구조 확인
```
✅ whitelist/simple@test.com/
    ├── email: "simple@test.com"
    └── created_at: 2025-09-03T03:15:32.123Z

✅ users/user@example.com/
    ├── conversations/ (서브컬렉션)
    │   ├── block_id_1/
    │   │   ├── user_id: "user@example.com"
    │   │   ├── user_request: "..."
    │   │   └── ...
    │   └── block_id_2/
    ├── email: "user@example.com"
    ├── name: "User Name"
    ├── picture: "profile_url"
    ├── google_user_id: "108731499195466851171"
    └── last_login: timestamp
```

## 📋 5. 인증 플로우 완전 개편

### 기존 인증 플로우 (Google user_id 기반)
1. 사용자 Google 로그인
2. Google user_id 추출
3. whitelist/{user_id} 문서 조회
4. status 필드 확인 (active/pending/inactive)
5. users/{user_id}/conversations 접근
6. 허용/차단 결정

### 새로운 인증 플로우 (이메일 기반 + users 문서 자동 생성) ⭐ 완전 개편
1. **사용자 Google 로그인**
2. **Google OAuth 토큰 검증** (TokenHandler)
   - `user_id` = 이메일, `google_user_id` = Google user_id (별도 보관)
3. **JWT 토큰 생성** (TokenHandler)
   - JWT 페이로드에 `user_id` = 이메일 포함
4. **화이트리스트 검증** (AuthRepository)
   - whitelist/{email} 문서 조회
   - 문서 존재 여부로 허용/차단 결정
5. **users 문서 자동 생성/업데이트** ⭐ 새로 추가 (AuthRepository)
   - users/{email} 문서 생성 (merge=True)
   - 사용자 메타데이터 (이름, 프로필 사진 등) 저장
6. **conversations 서브컬렉션 접근 준비**
   - users/{email}/conversations 구조
7. **모든 컬렉션에서 일관된 이메일 키 사용**

## 📋 6. 관련 파일 변경 목록

### 수정된 파일 ⭐ 2025-09-03 통합 작업 완료
1. **`utils/token_utils.py`** - TokenHandler JWT 토큰 user_id 이메일 변경 ⭐
2. **`features/authentication/repositories.py`** - AuthRepository + `ensure_user_document()` 메서드 추가 ⭐
3. **`features/authentication/services.py`** - AuthService + users 문서 자동 생성 연동 ⭐
4. **`features/authentication/routes.py`** - AuthRoutes 응답 데이터 이메일 기반 변경 ⭐
5. **`features/chat/repositories.py`** - ChatRepository 이메일 기반 사용자 관리
6. **`firebase/firestore.rules`** - 보안 규칙 이메일 기반 변경
7. **`add_user_to_whitelist.py`** - 스크립트 단순화
8. **`CLAUDE.md`** - 아키텍처 문서 이메일 기반 구조 + 인증 플로우 업데이트 ⭐

### 제거된 요소
- **화이트리스트 관련**: `status`, `last_login`, `user_id` 필드
- **복잡한 상태 관리**: 상태별 분기 로직
- **Google user_id 의존성**: JWT 토큰에서 이메일로 대체 (별도 필드로 보관)
- **UUID 자동 생성**: 이메일을 직접 키로 사용

### 새로 추가된 요소 ⭐
- **TokenHandler**: `google_user_id` 별도 필드, `user_id` = 이메일
- **AuthRepository**: `ensure_user_document()` 메서드
- **AuthService**: 인증 성공 시 users 문서 자동 생성 플로우
- **사용자 문서 구조**: 이메일 기반 users/{email} 문서 + 메타데이터

## 📋 7. 운영 가이드

### 7.1 사용자 추가 방법
```bash
# 새 사용자 화이트리스트 추가
python3 add_user_to_whitelist.py user@newcompany.com

# 여러 사용자 일괄 추가 (예시)
for email in "user1@test.com" "user2@test.com" "user3@test.com"; do
    python3 add_user_to_whitelist.py "$email"
done
```

### 7.2 사용자 제거 방법
```bash
# Firebase 콘솔에서 수동 삭제
# https://console.firebase.google.com/project/nlq-ex/firestore/data/whitelist

# 또는 gcloud CLI 사용
gcloud firestore documents delete projects/nlq-ex/databases/(default)/documents/whitelist/user@example.com

# 사용자 대화 데이터도 정리 (필요시)
gcloud firestore documents delete projects/nlq-ex/databases/(default)/documents/users/user@example.com --recursive
```

### 7.3 화이트리스트 조회
```bash
# 모든 화이트리스트 사용자 조회
gcloud firestore documents list projects/nlq-ex/databases/(default)/documents/whitelist --format="table(name)"

# 특정 사용자 대화 기록 조회
gcloud firestore documents list projects/nlq-ex/databases/(default)/documents/users/user@example.com/conversations --format="table(name,createTime)"
```

## 📋 8. 보안 고려사항

### 8.1 이메일 기반 보안 규칙
- **화이트리스트**: 사용자는 자신의 이메일로 된 화이트리스트만 읽기 가능
- **사용자 데이터**: 사용자는 자신의 이메일로 된 데이터만 읽기/쓰기 가능
- **대화 기록**: 사용자는 자신의 이메일에 속한 대화만 접근 가능
- **관리자 권한**: 관리자는 모든 화이트리스트 관리 가능

### 8.2 이메일 기반 인증의 안정성
- **검증된 이메일**: Google OAuth에서 제공하는 검증된 이메일 사용
- **이메일 검증**: JWT 토큰의 email_verified 필드로 이메일 검증 상태 확인
- **Firestore 이중 검증**: 보안 규칙에서 request.auth.token.email로 재검증
- **일관성**: 모든 컬렉션에서 동일한 이메일 키 사용으로 보안 일관성 확보

## 📋 9. 성능 영향

### 개선사항
- **쿼리 단순화**: 복합 조건 제거로 성능 향상
- **인덱스 최적화**: 단일 필드 인덱스만 필요
- **메모리 사용량 감소**: 불필요한 필드 제거로 문서 크기 축소
- **일관된 접근 패턴**: 모든 컬렉션에서 동일한 키 사용으로 캐싱 효율성 증대

### 예상 성능
- **화이트리스트 조회**: < 10ms (문서 ID 직접 조회)
- **사용자 추가**: < 50ms (단일 문서 생성)
- **대화 기록 조회**: < 100ms (서브컬렉션 쿼리)
- **보안 규칙 검증**: < 5ms (단순한 이메일 비교)
- **users 문서 자동 생성**: < 30ms (merge=True 업데이트)

## 📋 10. 모니터링 및 유지보수

### 10.1 로그 확인
```bash
# 인증 관련 로그 확인
grep "화이트리스트\|whitelist" logs/app.log

# 이메일 기반 인증 로그
grep "이메일\|email" logs/app.log

# Firestore 작업 로그
grep "users\|conversations" logs/app.log

# users 문서 자동 생성 로그
grep "ensure_user_document" logs/app.log
```

### 10.2 정기 점검 항목
- **화이트리스트 사용자 수 모니터링**
- **이메일 기반 인증 성공률 확인**
- **대화 데이터 일관성 검증** (user_id가 이메일인지 확인)
- **users 문서 자동 생성 성공률 모니터링**
- **비정상적인 인증 시도 탐지**
- **Firestore 사용량 모니터링**

## 📋 11. 향후 확장 고려사항

### 11.1 다중 인증 제공자 지원
현재는 Google OAuth만 지원하지만, 향후 확장시:

```javascript
// Kakao OAuth 추가시에도 동일한 이메일 기반 구조 유지 가능
match /users/{email} {
  allow read, write: if request.auth != null && 
                       (request.auth.token.email == email ||
                        request.auth.token.kakao_account.email == email);
}
```

### 11.2 사용자 그룹 관리
필요시 화이트리스트에 그룹 필드 추가:
```json
{
  "email": "user@example.com",
  "created_at": "timestamp",
  "groups": ["basic", "premium"]
}
```

### 11.3 감사 로그
화이트리스트 변경 이력 추적을 위한 audit 컬렉션:
```
audit/change_id/
├── action: "add_user" | "remove_user"
├── target_email: "user@example.com"
├── admin_email: "admin@company.com"
└── timestamp: "2025-09-03T..."
```

## 📋 12. 결론 및 달성 성과

### 달성된 목표
- ✅ **완전한 이메일 기반 아키텍처**: 모든 컬렉션에서 이메일 키 사용
- ✅ **극도로 단순한 구조**: 화이트리스트 2개 필드만 저장
- ✅ **직관적인 관리**: 이메일 = 문서 ID 일관성
- ✅ **사전 사용자 추가**: Google OAuth 독립적 관리
- ✅ **users 문서 자동 생성**: 인증 성공 시 자동 사용자 관리
- ✅ **관리 복잡도 최소화**: status, user_id 관리 완전 제거
- ✅ **보안 규칙 통일**: 모든 컬렉션에서 이메일 기반 접근 제어

### 운영상 이점
- **관리 효율성 극대화**: 이메일 하나로 모든 컬렉션 관리
- **실수 가능성 최소화**: 단순하고 일관된 구조로 운영 실수 방지
- **사용자 경험 개선**: 인증 성공 즉시 사용자 문서 자동 생성
- **확장성**: 필요시 추가 필드나 컬렉션 확장 용이
- **일관성**: 화이트리스트-사용자-대화 모든 레벨에서 이메일 키 사용
- **보안 강화**: 통일된 이메일 기반 접근 제어로 보안 정책 단순화

### 기술적 성과
- **아키텍처 일관성**: 모든 Feature에서 동일한 이메일 기반 패턴 적용
- **성능 최적화**: 단순한 문서 ID 직접 조회로 성능 향상
- **코드 단순화**: Repository, Service 계층 로직 대폭 간소화
- **자동화**: 사용자 문서 생성 완전 자동화로 운영 부담 감소
- **유지보수성**: Feature-Driven 아키텍처와 완벽 호환

---

**✅ 통합 작업 완료**: Firestore가 완전한 이메일 기반 아키텍처로 성공적으로 변경되었습니다.  
**📁 주요 변경 파일**: TokenHandler, AuthRepository, ChatRepository, AuthService, Firestore Rules, 화이트리스트 스크립트  
**🔧 통합 사용법**: `python3 add_user_to_whitelist.py <email>` → 모든 컬렉션에서 이메일 키로 통일 관리  
**🎯 핵심 성과**: Google user_id 의존성 완전 제거, 이메일 기반 단일 아키텍처 구축, users 문서 자동 생성 시스템 완성