# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고할 수 있는 가이드를 제공합니다.

## 프로젝트 개요

**AAA** (Natural Language Data Analysis Assistant)는 사용자가 자연어를 사용하여 BigQuery 데이터셋을 조회할 수 있는 풀스택 웹 애플리케이션입니다. 시스템은 Google 인증이 포함된 Flask 백엔드와 Next.js 프런트엔드로 구성되어 있으며, 인증된 사용자가 대화형 AI를 통해 데이터 분석을 수행할 수 있도록 설계되었습니다.

## 아키텍처

### 백엔드 (Python/Flask)
- **메인 진입점**: `backend/app.py` - 포괄적인 에러 핸들링과 CORS 설정이 포함된 Flask 애플리케이션
- **인증 시스템**: JWT 토큰을 사용한 Google OAuth 통합 (`utils/auth_utils.py`)
- **BigQuery 통합**: 쿼리 실행 및 메타데이터 검색을 위한 모듈화된 BigQuery 클라이언트 (`utils/bigquery/`)
- **LLM 처리**: 중앙화된 프롬프트 관리가 포함된 Anthropic Claude 통합 (`utils/llm_client.py`)
- **라우트 구성**: `routes/` 디렉토리의 블루프린트 (auth, chat, system routes)
- **프롬프트 시스템**: 일관된 LLM 상호작용을 위한 `utils/prompts/`의 JSON 기반 프롬프트 템플릿

### 프런트엔드 (Next.js/React/TypeScript)
- **프레임워크**: Next.js 15.4.5 with React 19, TypeScript, Tailwind CSS
- **상태 관리**: 인증용 Zustand 스토어 (`useAuthStore.ts`)와 채팅용 (`useChatStore.ts`)
- **컴포넌트**: 채팅 인터페이스, 인증, 사용자 관리를 위한 모듈형 React 컴포넌트
- **인증**: 세션 관리가 포함된 Google Sign-In 통합
- **스타일링**: 커스텀 타이포그래피 플러그인이 포함된 Tailwind CSS
- **코딩 규칙**: ESLint @typescript-eslint/no-explicit-any 규칙을 준수하여 명시적 타입 정의 필수

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

### 2. 중앙화된 프롬프트 관리
- `backend/utils/prompts/`의 JSON 기반 프롬프트 템플릿
- 카테고리: classification, sql_generation, data_analysis, guides, improvements
- 폴백 메커니즘이 포함된 템플릿 변수 치환
- 프롬프트 개발을 위한 핫-리로드 기능

### 3. 인증 및 권한 부여
- 모든 API 엔드포인트에 Google 인증 필수
- 리프레시 토큰이 포함된 JWT 기반 세션 관리
- 사용자 프로필 관리 및 대화 기록

### 4. 채팅 인터페이스
- Server-Sent Events (SSE)를 사용한 실시간 스트리밍 응답
- 대화 복원 및 메시지 기록
- 장시간 실행되는 쿼리용 진행률 표시기
- 포맷된 응답을 위한 마크다운 렌더링

## 데이터베이스 통합

- **주요**: 데이터 쿼리 및 메타데이터용 Google BigQuery
- **대화 저장**: 채팅 기록 지속성을 위한 BigQuery 테이블
- **스키마**: 메타데이터 추출이 포함된 유연한 스키마 처리
- **기본 데이터셋**: 예시용 `nlq-ex.test_dataset.events_20210131`

## 코드 작성 기준

- **파일 크기 관리**: 500라인을 넘으면 3개 이하의 파일로 분할, 파일이 너무 많아지면 별도 서비스 분리 고려
- **프로젝트 범위 관리**: 한 프로젝트에서 너무 많은 기능을 담는 것을 지양, 기능이 많아지면 기능 축소 또는 별도 프로젝트 생성
- **타입 안전성**: 프런트엔드에서 ESLint @typescript-eslint/no-explicit-any 규칙 준수

## 테스트 및 품질

- **프런트엔드**: 코드 품질을 위한 ESLint 설정
- **백엔드**: 포괄적인 에러 핸들링 및 로깅
- **인증**: 보안 토큰 검증 및 리프레시 메커니즘
- **CORS**: 개발 및 프로덕션 환경용 설정

## 배포 참고사항

- **프런트엔드**: Vercel 배포용 설정 (`vercel.json`)
- **백엔드**: Docker 지원 (`Dockerfile`) 및 프로덕션용 Gunicorn
- **환경**: 개발 및 프로덕션용 별도 설정
- **모니터링**: 타임스탬프 및 에러 추적이 포함된 구조화된 로깅