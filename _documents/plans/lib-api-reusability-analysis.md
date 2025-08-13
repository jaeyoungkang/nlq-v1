# lib/api 코드 재사용성 분석 보고서

## 현재 상태 분석

### lib/api.ts 구조
```typescript
// 현재 구조
const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});
```

### 현재 사용 패턴 분석

#### 1. 일관된 사용 패턴을 보이는 영역
- **useAuth.ts**: `api.get('/api/auth/verify')`, `api.post('/api/auth/google-login')` 등에서 일관된 사용
- **토큰 관리**: 모든 요청에 자동으로 Bearer 토큰 헤더 추가

#### 2. 혼재된 사용 패턴을 보이는 영역
- **useChat.ts**: 
  - SSE 스트리밍: `fetch()` API 직접 사용 (line 88-96)
  - 기존 HTTP 통신: `axios.post()` 직접 사용 (line 264)
  - **문제점**: `api` 인스턴스 대신 독립적인 axios와 fetch 사용

#### 3. 독립적 구현을 사용하는 영역
- **apply/page.tsx**: `fetch('/api/prototype-apply')` 직접 사용 (line 44)
- **app/api/prototype-apply/route.ts**: Next.js API Routes (서버사이드)

## 재사용성 향상 방안

### 1. 즉시 적용 가능한 개선사항

#### A. useChat.ts의 HTTP 요청 통일
```typescript
// 현재 (line 264)
const response = await axios.post(`${API_URL}/api/chat`, requestData);

// 개선안
const response = await api.post('/api/chat', requestData);
```

#### B. SSE 요청의 토큰 관리 개선
```typescript
// 현재 (line 88-96)
const token = Cookies.get('access_token');
const response = await fetch(`${API_URL}/api/chat-stream`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    // ...
  }
});

// 개선안: api 인스턴스의 baseURL과 interceptor 활용
const token = Cookies.get('access_token');
const response = await fetch(`${api.defaults.baseURL}/api/chat-stream`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    // ...
  }
});
```

#### C. apply 페이지의 API 호출 개선
```typescript
// 현재 (apply/page.tsx line 44)
const res = await fetch("/api/prototype-apply", { 
  method: "POST", 
  headers: { "Content-Type": "application/json" }, 
  body: JSON.stringify(values) 
});

// 개선안: 일관된 에러 처리를 위해 api 인스턴스 활용 가능
// (단, Next.js API Routes는 상대 경로 사용이 일반적이므로 현재 구현도 적절함)
```

### 2. 구조적 개선 방안

#### A. API 클라이언트 확장
```typescript
// lib/api.ts 확장 제안
import axios from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// 기본 HTTP 클라이언트
const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// SSE 전용 헬퍼
export const createSSERequest = (endpoint: string) => {
  const token = Cookies.get('access_token');
  return fetch(`${API_URL}${endpoint}`, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
    }
  });
};

export default api;
export { API_URL };
```

#### B. 타입 정의 중앙화
```typescript
// lib/types/api.ts (신규 파일 제안)
export interface SSEProgressEvent {
  stage: string;
  message: string;
  generated_sql?: string;
}

export interface SSEResultEvent {
  success: boolean;
  request_id: string;
  conversation_id: string;
  result: {
    type: string;
    content?: string;
    generated_sql?: string;
    data?: Record<string, unknown>[];
    row_count?: number;
  };
  // ... 기타 프로퍼티
}
```

### 3. 적용 우선순위

#### 높음 (즉시 적용 권장)
1. **useChat.ts의 axios 호출 통일**: `axios.post` → `api.post`
2. **SSE baseURL 통일**: 하드코딩된 `API_URL` → `api.defaults.baseURL`

#### 중간 (점진적 적용)
1. **SSE 헬퍼 함수 도입**: 토큰 관리 로직 중앙화
2. **에러 처리 표준화**: api 인스턴스의 interceptor 활용

#### 낮음 (장기적 고려)
1. **타입 정의 중앙화**: 별도 파일로 분리
2. **Next.js API Routes 통합**: 클라이언트 코드와 일관성 있는 패턴 도입

## 결론

현재 `lib/api.ts`는 **기본적인 토큰 관리와 baseURL 설정**에서는 재사용성이 높지만, 다음 영역에서 개선이 필요합니다:

1. **일관성 부족**: useChat.ts에서 혼재된 HTTP 클라이언트 사용
2. **중복 코드**: SSE 요청에서 토큰 관리 로직 중복
3. **타입 분산**: API 응답 타입이 각 파일에 분산 정의

**권장사항**: 즉시 적용 가능한 개선사항부터 점진적으로 적용하여 코드 일관성과 유지보수성을 향상시키는 것이 바람직합니다.