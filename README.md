# nlq-v1 (Natural Language Query v1)

**Analytics Assistant AI (AAA)**는 사용자가 자연어를 사용하여 BigQuery 데이터셋을 조회할 수 있는 풀스택 웹 애플리케이션입니다. Google OAuth 인증이 통합된 Flask 백엔드와 Next.js 프런트엔드로 구성되어 있으며, 인증된 사용자가 대화형 AI를 통해 데이터 분석을 수행할 수 있도록 설계되었습니다.

## 아키텍처

### 백엔드 (Python/Flask)
- **메인 진입점**: `backend/app.py` - 포괄적인 에러 핸들링과 CORS 설정이 포함된 Flask 애플리케이션
- **인증 시스템**: JWT 토큰을 사용한 Google OAuth 통합 (`utils/auth_utils.py`)
- **BigQuery 통합**: 쿼리 실행 및 메타데이터 검색을 위한 모듈화된 BigQuery 클라이언트 (`utils/bigquery/`)
- **LLM 처리**: 중앙화된 프롬프트 관리가 포함된 Anthropic Claude 통합 (`utils/llm_client.py`)
- **라우트 구성**: `routes/` 디렉토리의 블루프린트 (auth, chat, system routes)
- **프롬프트 시스템**: 일관된 LLM 상호작용을 위한 `utils/prompts/`의 JSON 기반 프롬프트 템플릿

### 프런트엔드 (Next.js/React/TypeScript)
- **프레임워크**: Next.js 15.4.5, React 19, TypeScript 5
- **상태 관리**: Zustand 스토어 (`useAuthStore.ts`, `useChatStore.ts`, `useNotificationStore.ts`)
- **컴포넌트**: 모듈형 React 컴포넌트 (채팅 인터페이스, 인증, 사용자 관리)
- **UI 라이브러리**: Tailwind CSS, Heroicons, Lucide React
- **인증**: Google Sign-In 통합 및 JWT 세션 관리
- **기타**: ESLint 설정, 마크다운 렌더링, 이메일 서비스 (Resend)

## 개발 명령어

### 프런트엔드 개발
```bash
cd frontend
npm run dev          # 개발 서버 시작 (http://localhost:3000)
npm run build        # 프로덕션 빌드
npm run start        # 프로덕션 서버 시작
npm run lint         # ESLint 실행
```

### 백엔드 개발
```bash
cd backend
python3 -m venv venv  # 가상 환경 생성
source venv/bin/activate  # 가상 환경 활성화
python app.py        # Flask 개발 서버 시작 (port 8080)
pip install -r requirements.txt  # 의존성 설치
```

## 주요 환경 설정

백엔드는 다음 환경 변수들을 필요로 합니다 (일반적으로 `.env.local`에 설정):
- `ANTHROPIC_API_KEY`: Claude LLM 통합용
- `GOOGLE_CLOUD_PROJECT`: BigQuery 프로젝트 ID
- `BIGQUERY_LOCATION`: 기본값 'asia-northeast3'
- `ALLOWED_ORIGINS`: CORS 오리진, 기본값 'http://localhost:3000'
- `FLASK_ENV`: 디버그 모드를 위해 'development'로 설정

## 핵심 기능

### 1. 자연어 쿼리 처리
- 사용자 입력을 카테고리별로 분류 (query_request, metadata_request, data_analysis, guide_request, out_of_scope)
- BigQuery 전용 프롬프트를 사용하여 Claude로 자연어에서 SQL 생성
- SSE를 통한 결과 스트리밍으로 BigQuery 쿼리 실행

### 2. 대화 컨텍스트 지원
- 이전 대화 기록을 활용한 연속적 대화 처리
- 컨텍스트 기반 입력 분류 및 LLM 중심 처리 방식
- SQL 패턴 재사용 및 점진적 쿼리 개선
- 이전 분석 결과를 참조한 심화 분석

### 3. 중앙화된 프롬프트 관리
- `backend/utils/prompts/`의 JSON 기반 프롬프트 템플릿
- 카테고리: classification, sql_generation, data_analysis, guides, improvements
- 컨텍스트 지원 템플릿 (`system_prompt_with_context`, `user_prompt_with_context`)
- 폴백 메커니즘이 포함된 템플릿 변수 치환

### 4. 통합된 인증 및 에러 처리
- Google OAuth 인증과 JWT 토큰 관리 (`auth_utils.py`)
- 표준화된 에러 응답 (`ErrorResponse`, `SuccessResponse` 클래스)
- 일관된 로깅 시스템 (`utils/logging_utils.py`)
- 모든 API 엔드포인트에 인증 보안 적용

### 5. 실시간 채팅 인터페이스
- Server-Sent Events (SSE) 기반 스트리밍 응답
- 사용자별 대화 관리 (user_id 기반)
- 대화 복원 및 메시지 기록 관리
- 마크다운 렌더링 및 글로벌 알림 시스템

## 데이터베이스 및 스토리지

- **주요 데이터**: Google BigQuery를 통한 데이터 쿼리 및 메타데이터 처리
- **대화 관리**: user_id 기반 채팅 기록 저장 및 조회
- **스키마 구조**: conversations, query_results 테이블
- **컨텍스트 처리**: 최근 대화 기록 기반 LLM 컨텍스트 제공
- **샘플 데이터**: `nlq-ex.test_dataset.events_20210131`

## 코드 작성 기준

### 기본 원칙
- **파일 크기 관리**: 500라인을 넘으면 3개 이하의 파일로 분할, 파일이 너무 많아지면 별도 서비스 분리 고려
- **프로젝트 범위 관리**: 한 프로젝트에서 너무 많은 기능을 담는 것을 지양, 기능이 많아지면 기능 축소 또는 별도 프로젝트 생성
- **타입 안전성**: 프런트엔드에서 ESLint @typescript-eslint/no-explicit-any 규칙 준수
- **최소한의 코드 원칙**: 현재 사용되지 않는 코드는 작성하지 않음. 향후 확장을 고려한 코드, 부가적인 유틸리티 등 즉시 필요하지 않은 코드는 배제하고 필요 시점에 구현

### 에러 처리 및 로깅 표준
- **통합 에러 응답**: `ErrorResponse`, `SuccessResponse` 클래스 사용
- **표준 로깅**: `utils/logging_utils.py`의 `get_logger()` 함수
- **규칙 문서**: `_documents/rules/ERROR_HANDLING_AND_LOGGING_RULES.md`
- **금지사항**: 직접 딕셔너리 응답, 기본 logging 모듈 사용

## 주요 기술 스택

### 백엔드
- **Python**: Flask 2.3.3, Flask-CORS 4.0.0
- **AI/ML**: Anthropic Claude API (≥0.59.0)
- **클라우드**: Google Cloud BigQuery 3.11.4, Google Auth
- **인증**: PyJWT 2.8.0, Google OAuth
- **서버**: Gunicorn 21.2.0 (프로덕션)

### 프런트엔드  
- **React**: Next.js 15.4.5, React 19, TypeScript 5
- **상태관리**: Zustand 5.0.7
- **UI**: Tailwind CSS, Heroicons, Lucide React
- **통신**: Axios 1.11.0, Server-Sent Events
- **기타**: React Markdown, Resend (이메일)

## 배포 및 설정

- **프런트엔드**: Vercel 배포 (`vercel.json`)
- **백엔드**: Docker 지원 (`Dockerfile`)
- **환경변수**: `.env.local` 파일 설정
- **로깅**: 구조화된 에러 추적 시스템