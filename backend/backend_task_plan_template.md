# 백엔드 개발 계획서 작성 지침

> nlq-v1 백엔드 개발을 위한 체계적 분석 및 계획 방법론  
> **리팩토링, 신규 기능 개발, 아키텍처 개선 등 모든 개발 작업에 적용**  
> **개발 표준은 CLAUDE.md 참조** - 이 문서는 순수하게 계획 프로세스에 집중

## 📋 계획서 구성 요소

### 1. 포괄적 현황 분석 (필수)
#### 1.1 대상 분석
- **주 대상 파일**: 위치, 크기(라인 수), 주요 클래스/함수
- **관련 파일/폴더 전체 조사**:
  - 대상이 import하는 모든 모듈
  - 대상을 import하는 모든 코드
  - 같은 디렉토리의 관련 파일/폴더
  - 관련 테스트, 문서, 설정 파일
- **데이터베이스 구조**: Firestore 컬렉션 및 문서 구조 확인
  - `whitelist/` : 인증된 사용자 화이트리스트
  - `users/{user_id}/conversations/` : 사용자별 대화 기록

#### 1.2 문제 정의
- **아키텍처 문제**: 모놀리식 구조, 계층 분리 미흡 등
- **의존성 문제**: 순환 참조, 과도한 결합 등
- **확장성 문제**: 새 기능 추가 시 어려움

### 2. 아키텍처 원칙 검토
#### 2.1 각 컴포넌트 분류
각 파일/모듈을 다음 기준으로 분류:
- **core**: 도메인 모델, 비즈니스 자산, 인프라 인터페이스
- **features**: 구체적 구현, 비즈니스 로직
- **utils**: 범용 유틸리티 (도메인 독립적)

#### 2.2 분류 근거 제시
| 컴포넌트 | 현재 위치 | 제안 위치 | 근거 |
|---------|----------|----------|------|
| AuthRepository | features/authentication/ | features/authentication/ | 인증 기능 전용 |
| ChatRepository | features/chat/ | features/chat/ | 대화 기능 전용 |
| FirestoreClient | core/repositories/ | core/repositories/ | 인프라 계층 공유 자산 |

### 3. 목표 구조 (ASCII 트리)
```
core/                     # 도메인 자산과 인터페이스
├── models/              # 공유 도메인 모델
│   ├── context.py       # ContextBlock, BlockType
│   └── __init__.py      
└── repositories/        # 인프라 추상화
    ├── base.py          # BaseRepository (ABC)
    └── firestore_base.py # FirestoreRepository, FirestoreClient

features/
├── authentication/      # 인증 및 사용자 관리
│   ├── repositories.py  # AuthRepository (whitelist 컬렉션)
│   ├── services.py      # 인증 비즈니스 로직
│   └── routes.py        # /api/auth/* 엔드포인트
├── chat/               # 대화 관리
│   ├── repositories.py  # ChatRepository (users 컬렉션)
│   ├── services.py      # 채팅 비즈니스 로직
│   └── routes.py        # /api/chat-stream, /api/conversations/*
├── llm/                # LLM 통합
│   ├── models.py        # LLM 요청/응답 모델
│   └── services.py      # LLMService (Anthropic Claude)
└── system/             # 시스템 관리
    └── routes.py        # /api/system/*

utils/
├── token_utils.py      # JWT, Google OAuth 토큰 처리
├── logging_utils.py    # 표준화된 로깅
├── error_utils.py      # 표준 응답 클래스
└── time_utils.py       # 시간 표준화
```

### 4. 기능 매핑 (현재 → 목표)
- **기존 클래스/함수 → 새로운 위치**로 명확한 매핑 제시
- 각 기능이 어느 계층으로 이동하는지 명시
- "그대로 이관" vs "분리/통합" 구분

#### 4.1 Firestore 기반 Repository 패턴 적용
| 기존 구조 | 새 구조 | 변경 사항 |
|---------|---------|----------|
| BigQuery 기반 Repository | FirestoreRepository | NoSQL 문서 기반 구조로 변경 |
| 5개 Repository 클래스 | 2개 Repository 클래스 | AuthRepository, ChatRepository만 유지 |
| 테이블 기반 SQL 쿼리 | 컬렉션/문서 기반 조회 | Firestore 클라이언트 사용 |

### 5. 의존성 및 영향 범위 분석
#### 5.1 직접 의존성
- 대상을 사용하는 모든 코드 목록
- 각 사용처에서 필요한 변경사항

#### 5.2 간접 영향
- 테스트 코드 수정 필요성
- 문서 업데이트 필요성
- 설정 파일 변경 필요성

#### 5.3 하위 호환성
- 점진적 마이그레이션 필요 여부
- 임시 Adapter 패턴 필요 여부

### 6. 마이그레이션 단계
1. **인프라 기반 구축**: FirestoreClient, FirestoreRepository 구현
2. **Base Repository 추상화**: BaseRepository를 ABC로 변경
3. **Repository 구현**: AuthRepository, ChatRepository Firestore 기반으로 변경
4. **Service 계층 적용**: 의존성 주입 패턴 적용
5. **컬렉션 구조 설계**: whitelist, users 컬렉션 분리
6. **라우트 단순화**: 필수 엔드포인트만 유지
7. **의존성 연결**: app.py에서 Firestore 기반 초기화
8. **레거시 정리**: BigQuery 관련 코드 제거

#### 6.1 Firestore 특화 마이그레이션 고려사항
- **컬렉션 설계**: 인증(whitelist)과 대화(users)의 명확한 분리
- **문서 ID 표준화**: Google OAuth user_id 기준 통일
- **서브컬렉션 활용**: users/{user_id}/conversations 구조
- **배치 작업**: 대량 데이터 이관 시 Firestore 배치 API 활용

### 7. 구현 시 준수사항

#### 7.1 개발 표준 준수
- **CLAUDE.md 필수 참조**: 아키텍처 원칙, API 계약, 에러 처리 등 모든 개발 표준
- **계획 단계에서 확인**: 설계가 CLAUDE.md 기준을 충족하는지 사전 검토

#### 7.2 도메인 모델 고려사항
- **ContextBlock 설계**: CLAUDE.md의 ContextBlock 설계 원칙 준수 확인
- **데이터 모델**: 공유 모델과 기능별 모델 적절한 분리
- **유틸리티 활용**: 모델 전용 헬퍼 함수 활용 계획

#### 7.3 Firestore 특화 개발 원칙
- **NoSQL 설계**: 관계형 데이터베이스와 다른 문서 중심 구조 고려
- **컬렉션 그룹 쿼리**: 여러 사용자의 데이터를 효율적으로 조회
- **실시간 리스너**: 필요 시 실시간 데이터 동기화 활용
- **보안 규칙**: Firestore Security Rules를 통한 데이터 접근 제어
- **인덱스 최적화**: 복합 쿼리를 위한 인덱스 설계

## 📊 구현 완료 후 추가 내용

### 8. 실제 구현 완료 섹션
```markdown
## 실제 구현 완료 (YYYY-MM-DD)

### ✅ 완료된 작업 내역 (Firestore 마이그레이션 예시)
#### 1. 인프라 기반 구축
- ✅ FirestoreClient 싱글턴 패턴 구현 (`core/repositories/firestore_base.py`)
- ✅ FirestoreRepository 기본 클래스 구현
- ✅ BaseRepository ABC 추상화 (`core/repositories/base.py`)

#### 2. Repository 계층 변경
- ✅ AuthRepository → whitelist 컬렉션 전용 (`features/authentication/repositories.py`)
- ✅ ChatRepository → users 컬렉션 전용 (`features/chat/repositories.py`)
- ✅ 기존 5개 Repository → 2개로 단순화

#### 3. 컬렉션 구조 설계
- ✅ `whitelist/` : 인증된 사용자 화이트리스트
- ✅ `users/{user_id}/conversations/` : 사용자별 대화 기록
- ✅ Google OAuth user_id 기준 문서 ID 표준화

#### 4. 의존성 주입 단순화
- ✅ app.py에서 AuthRepository, ChatRepository만 초기화
- ✅ BigQuery 관련 테이블 초기화 코드 제거
- ✅ Firestore 클라이언트 환경변수 기반 초기화

### 📊 구현 결과
#### 아키텍처 준수
- ✅ Controller → Service → Repository 계층 흐름
- ✅ 표준 응답/로깅/인증 적용
- ✅ Feature-Driven 모듈 구조 유지

#### Firestore 통합
- ✅ NoSQL 문서 기반 데이터 모델 적용
- ✅ 컬렉션별 역할 분리 (인증 vs 대화)
- ✅ 실시간 데이터 동기화 지원
- ✅ Google Cloud 생태계 통합

#### 코드 단순화
- ✅ Repository 클래스 60% 감소 (5개 → 2개)
- ✅ BigQuery 의존성 제거 (쿼리 실행 제외)
- ✅ 테이블 스키마 관리 불필요

```

## 🎯 작성 가이드라인

### 내용 원칙
1. **포괄성**: 관련된 모든 파일/폴더 조사 필수
2. **근거 제시**: 각 결정에 대한 명확한 이유
3. **구체성**: 파일명, 클래스명, 함수명까지 명시
4. **실행 가능성**: 단계별로 실제 수행 가능한 작업 정의
5. **표준 준수**: CLAUDE.md 아키텍처 기준 반드시 포함

### 작성 프로세스
1. **포괄적 조사**: 대상과 관련된 모든 요소 파악
   - "관련된 모든", "전체 구조" 키워드 활용
   - 직접/간접 의존성 모두 확인
2. **아키텍처 분류**: core/features/utils 적절성 판단
   - 도메인 자산 vs 유틸리티 구분
   - 현재 위치의 적절성도 재검토
3. **영향 분석**: 변경 시 영향받는 모든 부분 파악
4. **설계**: 목표 구조 및 기능 매핑 정의
5. **계획**: 상세 마이그레이션 단계 정의
6. **검토**: CLAUDE.md 준수사항 체크
7. **실행**: 단계별 구현 후 완료 내역 문서화

### 품질 체크리스트
- [ ] 관련된 모든 파일/폴더를 조사했는가?
- [ ] 각 컴포넌트의 core/features/utils 분류가 적절한가?
- [ ] 목표 구조가 기능 주도 아키텍처를 따르는가?
- [ ] 의존성 및 영향 범위를 완전히 파악했는가?
- [ ] **CLAUDE.md 개발 표준을 모두 검토했는가?**
  - [ ] 아키텍처 원칙 준수 계획이 있는가?
  - [ ] API 계약 및 에러 처리 표준 적용 계획이 있는가?
  - [ ] 도메인 모델 설계 원칙을 따르는가?
- [ ] **Firestore 특화 검토사항**
  - [ ] 컬렉션 구조가 비즈니스 도메인을 올바르게 반영하는가?
  - [ ] 문서 ID 설계가 확장 가능한가?
  - [ ] 쿼리 패턴이 Firestore 제약사항을 고려했는가?
  - [ ] 보안 규칙 설계 계획이 있는가?
- [ ] 누락된 요소가 없는지 재확인했는가?


#### LLM 지시사항 템플릿
Claude Code에게 리팩토링 작업 지시 시 다음 템플릿 활용:

```
"[대상] 리팩토링 작업을 수행하라.
1. CLAUDE.md의 개발 표준을 모두 준수하라
2. 계획서에 따라 단계별로 진행하라
3. 각 단계 완료 후 체크리스트 항목들을 확인하라
4. 문제가 발생하면 CLAUDE.md를 재참조하여 해결하라"
```

## 📚 참조 문서

- **[CLAUDE.md](./CLAUDE.md)**: 백엔드 개발 표준 (아키텍처 원칙, API 계약, 코딩 규칙)
- **이 문서**: 개발 계획 작성 방법론 (리팩토링 & 신규 기능 개발)

## 🎯 사용법

### 리팩토링 계획 시
- 섹션 A 중심으로 활용
- 기존 코드 분석 → 아키텍처 재구성 → 마이그레이션 계획

### 신규 기능 개발 계획 시  
- 섹션 B 중심으로 활용
- 요구사항 분석 → 아키텍처 설계 → 단계별 개발 계획

이 지침을 활용하여 체계적인 개발 계획서를 작성하고, 구현 시에는 CLAUDE.md를 참조하세요.