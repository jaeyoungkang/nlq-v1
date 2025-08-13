# 서버 예외 응답 GlobalNotification 일괄 처리 방법 검토

## 현재 상황 분석

### 1. 기존 에러 처리 방식

#### GlobalNotification 시스템
```typescript
// useNotificationStore.ts
interface NotificationState {
  message: string | null;
  type: 'error' | 'success' | 'info';
  setMessage: (message: string, type: 'error' | 'success' | 'info') => void;
  clearMessage: () => void;
}
```

#### 현재 에러 처리 패턴
- **분산된 처리**: 각 컴포넌트/훅에서 개별적으로 try-catch 구문으로 에러 처리
- **수동 알림**: 에러 발생 시 수동으로 `setMessage()` 호출
- **일관성 부족**: 에러 타입별 처리 방식이 다름

```typescript
// 현재 패턴 예시 (useAuth.ts)
catch (error) {
  if (isAxiosError(error) && error.response?.status === 403) {
    setWhitelistError({...}); // 특별 처리
  }
  // GlobalNotification 사용 안 함
}
```

### 2. 백엔드 에러 응답 체계

백엔드는 매우 체계적인 에러 응답을 제공합니다:

```json
{
  "success": false,
  "error": "사용자 친화적 메시지",
  "error_type": "분류_코드",
  "details": {
    "reason": "구체적_원인",
    "user_status": "상태정보"
  },
  "timestamp": "2025-08-13T10:30:45Z"
}
```

## 일괄 처리 방법 설계

### 1. Axios Response Interceptor 활용

#### A. API 클라이언트 확장
```typescript
// lib/api.ts 확장
import { useNotificationStore } from '../stores/useNotificationStore';

// Response Interceptor 추가
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 전역 에러 처리
    handleGlobalError(error);
    return Promise.reject(error);
  }
);

// 전역 에러 핸들러
const handleGlobalError = (error: AxiosError) => {
  const { setMessage } = useNotificationStore.getState();
  
  if (!error.response) {
    // 네트워크 에러
    setMessage('네트워크 연결을 확인해주세요', 'error');
    return;
  }

  const { status, data } = error.response;
  const errorData = data as ApiErrorResponse;

  // 에러 타입별 처리
  switch (errorData.error_type) {
    case 'token_expired':
      // 자동 토큰 갱신 시도
      handleTokenExpired();
      break;
    case 'access_denied':
      // 화이트리스트 에러는 특별 처리
      handleAccessDenied(errorData);
      break;
    case 'validation_error':
      // 입력 검증 에러
      setMessage(errorData.error, 'error');
      break;
    default:
      // 일반 에러
      setMessage(errorData.error || '오류가 발생했습니다', 'error');
  }
};
```

#### B. 에러 타입 정의 확장
```typescript
// lib/types/api.ts 확장
export interface ApiErrorResponse {
  success: false;
  error: string;
  error_type: string;
  details?: {
    reason?: string;
    user_status?: string;
    support_message?: string;
    debug_info?: any;
  };
  timestamp: string;
}

export interface ErrorHandlerConfig {
  showNotification?: boolean;
  notificationType?: 'error' | 'info' | 'success';
  customHandler?: (error: ApiErrorResponse) => void;
}
```

### 2. 컴포넌트별 에러 처리 최적화

#### A. 에러 처리 옵션 제공
```typescript
// 개별 API 호출에서 전역 처리 제어
const loginWithGoogle = async (credential: string) => {
  try {
    const response = await api.post('/api/auth/google-login', 
      { id_token: credential },
      { 
        // 커스텀 에러 처리 설정
        headers: { 'X-Error-Handling': 'custom' }
      }
    );
  } catch (error) {
    // 이미 interceptor에서 처리됨
    // 필요시 추가 로직만 작성
    if (isAxiosError(error) && error.response?.data.error_type === 'access_denied') {
      setWhitelistError(error.response.data);
    }
  }
};
```

#### B. SSE 에러 처리 통합
```typescript
// useChat.ts에서 SSE 에러도 GlobalNotification 연동
const handleSSEError = (errorEvent: SSEErrorEvent) => {
  const { setMessage } = useNotificationStore.getState();
  
  switch (errorEvent.error_type) {
    case 'token_expired':
      setMessage('로그인이 만료되었습니다. 다시 로그인해주세요', 'error');
      break;
    case 'service_error':
      setMessage('서비스에 일시적인 문제가 발생했습니다', 'error');
      break;
    default:
      setMessage(errorEvent.error, 'error');
  }
};
```

### 3. 에러 처리 레벨 구분

#### A. 자동 처리 (Silent)
- `token_expired`: 자동 토큰 갱신
- `service_error`: 재시도 로직
- 네트워크 타임아웃: 자동 재연결

#### B. 알림 표시 (Notification)
- `validation_error`: 입력 검증 실패
- `insufficient_permissions`: 권한 부족
- `not_found`: 리소스 없음
- 일반적인 서버 오류

#### C. 특별 처리 (Custom)
- `access_denied`: 화이트리스트 모달 표시
- `account_disabled`: 계정 상태 페이지 리다이렉트
- 결제 관련 에러: 결제 페이지로 이동

### 4. 구현 우선순위

#### 높음 (즉시 구현)
1. **Response Interceptor 추가**: 기본 에러 알림 자동화
2. **에러 타입별 분기**: 백엔드 `error_type` 활용한 처리
3. **SSE 에러 통합**: 스트리밍 에러도 GlobalNotification 연동

## 구현 예시

### 1. 확장된 API 클라이언트
```typescript
// lib/api.ts 완전 확장 버전
import axios from 'axios';
import Cookies from 'js-cookie';
import { useNotificationStore } from '../stores/useNotificationStore';
import { useAuthStore } from '../stores/useAuthStore';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080',
});

// Request Interceptor (기존)
api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response Interceptor (신규)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { setMessage } = useNotificationStore.getState();
    const { logout } = useAuthStore.getState();
    
    if (!error.response) {
      setMessage('네트워크 연결을 확인해주세요', 'error');
      return Promise.reject(error);
    }

    const { status, data } = error.response;
    const errorData = data as ApiErrorResponse;
    
    // 커스텀 에러 처리 제외 설정 확인
    if (error.config?.headers?.['X-Error-Handling'] === 'custom') {
      return Promise.reject(error);
    }

    switch (errorData.error_type) {
      case 'token_expired':
        setMessage('로그인이 만료되었습니다', 'info');
        logout();
        window.location.reload();
        break;
        
      case 'access_denied':
        // 화이트리스트 에러는 개별 처리에 맡김
        break;
        
      case 'validation_error':
      case 'service_error':
      case 'internal_error':
        setMessage(errorData.error || '오류가 발생했습니다', 'error');
        break;
        
      default:
        if (status >= 500) {
          setMessage('서버에 일시적인 문제가 발생했습니다', 'error');
        } else {
          setMessage(errorData.error || '오류가 발생했습니다', 'error');
        }
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

### 2. 사용 예시
```typescript
// useAuth.ts에서 간소화된 에러 처리
const loginWithGoogle = async (credential: string) => {
  try {
    setLoading(true);
    // 화이트리스트 에러는 커스텀 처리
    const response = await api.post('/api/auth/google-login', 
      { id_token: credential },
      { headers: { 'X-Error-Handling': 'custom' } }
    );
    
    if (response.status === 200 && response.data.success) {
      setToken(response.data.access_token);
      setUser(response.data.user);
      window.location.reload();
    }
  } catch (error) {
    // 화이트리스트 에러만 개별 처리
    if (isAxiosError(error) && error.response?.data.error_type === 'access_denied') {
      setWhitelistError(error.response.data);
    }
    // 기타 에러는 이미 interceptor에서 처리됨
  } finally {
    setLoading(false);
  }
};
```

## 기대 효과

### 1. 개발자 경험 향상
- **코드 중복 제거**: 반복적인 try-catch 구문 최소화
- **일관된 에러 처리**: 모든 API 호출에서 동일한 패턴
- **유지보수성**: 에러 처리 로직 중앙 관리

### 2. 사용자 경험 향상
- **즉각적인 피드백**: 모든 에러에 대한 알림 보장
- **일관된 UI**: 표준화된 에러 메시지 형식

## Header 컴포넌트 예외 처리 통합

### 현재 Header의 예외 처리 방식

Header 컴포넌트는 현재 독립적인 에러 표시 시스템을 가지고 있습니다:

```typescript
// Header.tsx - 현재 방식
const Header = () => {
  const { whitelistError, setWhitelistError } = useAuthStore();
  
  return (
    <header>
      {whitelistError && (
        <div className="mb-4 p-4 border rounded-lg bg-red-50 border-red-200">
          {/* 화이트리스트 에러 전용 UI */}
          <ExclamationCircleIcon />
          <h3>{whitelistError.reason === 'session_expired' ? '세션 만료' : '접근 권한 없음'}</h3>
          <p>{whitelistError.message}</p>
          {/* 에러 타입별 추가 안내 */}
        </div>
      )}
    </header>
  );
};
```

### 문제점 분석

1. **중복된 에러 UI**: Header의 whitelistError와 GlobalNotification이 동시에 표시될 수 있음
2. **일관성 부족**: 동일한 에러 타입(`access_denied`)에 대해 다른 UI 스타일
3. **관리 복잡성**: 에러 상태가 두 곳(AuthStore, NotificationStore)에 분산

### 통합 방안 설계

#### 방안 1: GlobalNotification 완전 통합

**WhitelistError를 GlobalNotification으로 통합:**

```typescript
// 수정된 Response Interceptor
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { setMessage } = useNotificationStore.getState();
    const errorData = error.response?.data;
    
    switch (errorData.error_type) {
      case 'access_denied':
        // Header 전용 에러도 GlobalNotification으로 처리
        const reason = errorData.details?.reason;
        let message = errorData.error;
        
        if (reason === 'not_whitelisted') {
          message += ' https://analytics.artificialmind.kr/ 에서 계정 등록을 요청하세요!';
        } else if (reason === 'pending_approval') {
          message += ' 관리자 승인 후 서비스를 이용하실 수 있습니다.';
        }
        
        setMessage(message, 'error');
        break;
    }
    
    return Promise.reject(error);
  }
);
```

```typescript
// 간소화된 Header.tsx
const Header = () => {
  const { isAuthenticated, isLoading } = useAuth();
  
  return (
    <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
      {/* whitelistError 관련 UI 제거 */}
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-3xl font-bold text-primary-700">Analytics Assistant AI</h1>
        
        <div className="flex items-center space-x-4">
          {isLoading ? (
            <div className="animate-pulse bg-gray-200 h-8 w-32 rounded"></div>
          ) : isAuthenticated ? (
            <UserProfile />
          ) : (
            <GoogleLoginButton />
          )}
        </div>
      </div>
    </header>
  );
};
```

#### 방안 2: 하이브리드 접근

**중요한 화이트리스트 에러는 Header에, 일반 에러는 GlobalNotification에:**

```typescript
// 확장된 NotificationStore
interface NotificationState {
  message: string | null;
  type: 'error' | 'success' | 'info';
  // 새로운 상태 추가
  criticalError: {
    type: 'whitelist' | 'auth' | null;
    data: any;
  } | null;
  
  setMessage: (message: string, type: 'error' | 'success' | 'info') => void;
  setCriticalError: (error: any) => void;
  clearMessage: () => void;
  clearCriticalError: () => void;
}
```

```typescript
// Header에서 criticalError 처리
const Header = () => {
  const { criticalError, clearCriticalError } = useNotificationStore();
  
  return (
    <header>
      {criticalError?.type === 'whitelist' && (
        <div className="mb-4 p-4 border rounded-lg bg-red-50 border-red-200">
          {/* 기존 화이트리스트 UI 유지 */}
        </div>
      )}
      
      {/* 나머지 Header 내용 */}
    </header>
  );
};
```

#### 방안 3: 스마트 에러 라우팅 (권장)

**에러 중요도와 타입에 따라 표시 위치 결정:**

```typescript
// 에러 분류 시스템
enum ErrorDisplayType {
  NOTIFICATION = 'notification',    // GlobalNotification (일반 에러)
  HEADER = 'header',               // Header 인라인 (중요 인증 에러)
  MODAL = 'modal',                 // 모달 (치명적 에러)
  PAGE = 'page'                    // 전체 페이지 (시스템 에러)
}

interface ErrorHandlingConfig {
  displayType: ErrorDisplayType;
  autoClose?: boolean;
  duration?: number;
  actions?: ErrorAction[];
}

const ERROR_CONFIGS: Record<string, ErrorHandlingConfig> = {
  'access_denied': {
    displayType: ErrorDisplayType.HEADER,
    autoClose: false,
  },
  'token_expired': {
    displayType: ErrorDisplayType.NOTIFICATION,
    autoClose: true,
    duration: 3000
  },
  'validation_error': {
    displayType: ErrorDisplayType.NOTIFICATION,
    autoClose: true,
    duration: 5000
  },
  'service_error': {
    displayType: ErrorDisplayType.NOTIFICATION,
    autoClose: true,
    duration: 4000
  }
};
```

```typescript
// 통합 에러 핸들러
const handleApiError = (error: ApiErrorResponse) => {
  const config = ERROR_CONFIGS[error.error_type] || {
    displayType: ErrorDisplayType.NOTIFICATION
  };
  
  switch (config.displayType) {
    case ErrorDisplayType.HEADER:
      // AuthStore의 whitelistError 설정
      useAuthStore.getState().setWhitelistError({
        message: error.error,
        errorType: error.error_type,
        reason: error.details?.reason,
        userStatus: error.details?.user_status
      });
      break;
      
    case ErrorDisplayType.NOTIFICATION:
      // GlobalNotification 표시
      useNotificationStore.getState().setMessage(
        error.error, 
        'error'
      );
      break;
      
    case ErrorDisplayType.MODAL:
      // 모달 에러 처리 (향후 구현)
      break;
  }
};
```

## 코드 간결화 중심 구현 계획 (업데이트)

### 현재 코드 복잡성 분석

**현재 에러 처리 코드 현황:**
- 9개 파일에서 총 73개의 에러 관련 코드 (try/catch, setError, setMessage 등)
- 각 컴포넌트/훅마다 반복적인 try-catch 구문
- 분산된 에러 처리 로직으로 인한 코드 중복

### 간결화 우선 구현 방안 (권장)

#### 방안: Response Interceptor 중심 통합

**목표: 모든 에러 처리를 API 레벨에서 자동 처리**

```typescript
// lib/api.ts - 완전 자동화된 에러 처리
import axios from 'axios';
import Cookies from 'js-cookie';
import { useNotificationStore } from '../stores/useNotificationStore';
import { useAuthStore } from '../stores/useAuthStore';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080',
});

// Request Interceptor
api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response Interceptor - 모든 에러 자동 처리
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // 커스텀 헤더로 자동 처리 건너뛰기 가능
    if (error.config?.headers?.['X-Skip-Global-Error'] === 'true') {
      return Promise.reject(error);
    }

    const errorData = error.response?.data;
    
    // 자동 에러 처리 - 코드 작성 불필요
    handleErrorAutomatically(errorData, error.response?.status);
    
    return Promise.reject(error);
  }
);

// 완전 자동화된 에러 핸들러
const handleErrorAutomatically = (errorData: any, status: number) => {
  const { setMessage } = useNotificationStore.getState();
  const { setWhitelistError, logout } = useAuthStore.getState();
  
  if (!errorData) {
    setMessage('네트워크 연결을 확인해주세요', 'error');
    return;
  }

  switch (errorData.error_type) {
    // 자동 로그아웃 + 알림
    case 'token_expired':
    case 'invalid_token':
      logout();
      setMessage('로그인이 만료되었습니다', 'info');
      window.location.reload();
      break;
      
    // Header 표시 (화이트리스트 에러만)
    case 'access_denied':
      setWhitelistError({
        message: errorData.error,
        errorType: errorData.error_type,
        reason: errorData.details?.reason,
        userStatus: errorData.details?.user_status
      });
      break;
      
    // GlobalNotification 표시 (모든 일반 에러)
    default:
      setMessage(errorData.error || '오류가 발생했습니다', 'error');
  }
};

export default api;
```

#### 간결해진 컴포넌트 코드

**Before (현재):**
```typescript
// useAuth.ts - 복잡한 에러 처리
const loginWithGoogle = async (credential: string) => {
  try {
    setLoading(true);
    const response = await api.post('/api/auth/google-login', requestData);
    
    if (response.status === 200 && response.data.success) {
      setToken(response.data.access_token);
      setUser(response.data.user);
      window.location.reload();
    }
  } catch (error) {
    console.error('❌ Google 로그인 실패:', error);
    if (isAxiosError(error)) {
      const errorData = error.response?.data;
      if (error.response?.status === 403 && errorData?.error_type === 'access_denied') {
        setWhitelistError({
          message: errorData.error || '접근이 거부되었습니다',
          errorType: errorData.error_type,
          reason: errorData.details?.reason,
          userStatus: errorData.details?.user_status
        });
      }
    }
  } finally {
    setLoading(false);
  }
};
```

**After (간결화):**
```typescript
// useAuth.ts - 간결한 코드
const loginWithGoogle = async (credential: string) => {
  setLoading(true);
  
  try {
    const response = await api.post('/api/auth/google-login', { id_token: credential });
    
    // 성공 케이스만 처리 - 에러는 interceptor가 자동 처리
    if (response.data.success) {
      setToken(response.data.access_token);
      setUser(response.data.user);
      window.location.reload();
    }
  } catch (error) {
    // 에러 처리는 이미 interceptor에서 완료됨 - 추가 코드 불필요
  } finally {
    setLoading(false);
  }
};
```

**Before (현재):**
```typescript
// useChat.ts - 복잡한 SSE 에러 처리
} catch (err: unknown) {
  let errorMessage = 'Failed to connect to the server.';

  if (isAxiosError(err)) {
    errorMessage = err.response?.data?.error || err.message;
    
    if (err.response?.status === 401) {
      errorMessage = '로그인이 필요합니다. 페이지를 새로고침하고 다시 로그인해주세요.';
    }
  } else if (err instanceof Error) {
    errorMessage = err.message;
  }

  console.error('❌ SSE Chat error:', errorMessage);
  setError(errorMessage);
  updateLastMessage({
    content: `Sorry, an error occurred: ${errorMessage}`,
    isProgress: false
  });
}
```

**After (간결화):**
```typescript
// useChat.ts - 간결한 SSE 에러 처리
} catch (err: unknown) {
  // SSE는 fetch API 사용이므로 수동 에러 처리 (하지만 간결하게)
  const { setMessage } = useNotificationStore();
  setMessage('채팅 연결에 문제가 발생했습니다', 'error');
  
  updateLastMessage({
    content: '연결이 끊어졌습니다. 새로고침 후 다시 시도해주세요.',
    isProgress: false
  });
}
```

### 코드 간결화 효과 예상

#### 제거되는 코드
1. **각 컴포넌트의 try-catch 블록**: 약 60% 감소
2. **에러 타입 분기 로직**: 중앙화로 95% 제거
3. **중복된 에러 메시지 처리**: 완전 제거
4. **토큰 만료 처리**: 자동화로 완전 제거

#### 예상 코드 감소량
```
현재: 73개 에러 관련 코드
예상: 15-20개 에러 관련 코드 (70% 감소)
```

### 간결화 우선 구현 단계

#### 1단계: Response Interceptor 구현 (즉시)
- 모든 API 에러를 자동 처리하는 interceptor 추가
- 기존 try-catch 블록의 에러 처리 로직 제거

#### 2단계: 컴포넌트 코드 정리 (1-2일)
- 각 컴포넌트에서 불필요한 에러 처리 코드 제거
- 성공 케이스만 남기고 나머지는 interceptor에 위임

#### 3단계: 특별 케이스 최적화 (필요시)
- SSE 에러 처리 간소화
- 화이트리스트 에러 자동화

### 예외적으로 수동 처리가 필요한 케이스

```typescript
// 특별한 에러 처리가 필요한 경우만 수동 처리
const specialApiCall = async () => {
  try {
    const response = await api.post('/special-endpoint', data, {
      headers: { 'X-Skip-Global-Error': 'true' }
    });
    return response;
  } catch (error) {
    // 특별한 로직이 필요한 경우만 수동 처리
    handleSpecialError(error);
  }
};
```

### 구현 권장사항 (간결화 중심)

#### 1. 최우선: 자동화
- **Response Interceptor**: 95% 에러를 자동 처리
- **표준화**: 모든 에러는 동일한 방식으로 처리
- **중앙화**: 에러 처리 로직을 한 곳에 집중

#### 2. 예외 최소화
- **수동 처리**: 정말 필요한 경우만 (예: 파일 업로드, 특별한 UX)
- **설정 가능**: `X-Skip-Global-Error` 헤더로 제어

#### 3. 단순한 컴포넌트  
- **성공 케이스만**: 각 컴포넌트는 성공 로직만 처리
- **에러 무관심**: 에러는 interceptor가 알아서 처리

## 최종 권장사항: 코드 간결화 우선

### 핵심 원칙
1. **95% 자동화**: Response Interceptor가 거의 모든 에러 처리
2. **5% 예외**: 정말 특별한 케이스만 수동 처리  
3. **0% 중복**: 에러 처리 로직의 중복 완전 제거

### 예상 효과
- **코드 라인 수**: 70% 감소 (73개 → 15-20개)
- **유지보수성**: 에러 처리 로직이 한 곳에 집중
- **일관성**: 모든 에러가 동일한 방식으로 처리
- **개발 속도**: 새로운 API 호출 시 에러 처리 코드 작성 불필요

이 접근 방식으로 전체 코드베이스가 훨씬 간결하고 유지보수하기 쉬워집니다.

### 이전 구현 권장사항 (참고용)

#### 2. 에러 표시 우선순위

```typescript
// 에러 표시 우선순위 정의
const ERROR_PRIORITY = {
  'access_denied': 1,      // Header (최고 우선순위)
  'token_expired': 2,      // Notification
  'service_error': 3,      // Notification
  'validation_error': 4    // Notification
};
```

#### 3. 사용자 경험 고려사항

- **화이트리스트 에러**: Header에 지속 표시 (해결될 때까지)
- **일반 에러**: GlobalNotification으로 임시 표시 (자동 닫힘)
- **중복 방지**: 동일한 에러는 한 곳에서만 표시
- **우선순위**: 더 중요한 에러가 있으면 덜 중요한 에러는 숨김

### 마이그레이션 코드 예시

```typescript
// useAuth.ts - 수정된 에러 처리
const loginWithGoogle = async (credential: string) => {
  try {
    const response = await api.post('/api/auth/google-login', 
      { id_token: credential }
    );
    // 성공 로직
  } catch (error) {
    // Response Interceptor가 자동으로 처리
    // 화이트리스트 에러는 이미 Header에 표시됨
    // 추가 로직 불필요
  } finally {
    setLoading(false);
  }
};
```

```typescript
// AuthStore - whitelistError 유지
export const useAuthStore = create<AuthState>((set) => ({
  // ... 기존 상태
  whitelistError: null,
  
  setWhitelistError: (whitelistError) => {
    // GlobalNotification 메시지가 있으면 제거
    useNotificationStore.getState().clearMessage();
    set({ whitelistError });
  },
  
  // ... 나머지 구현
}));
```

## 주의사항

1. **Performance**: Response interceptor로 인한 오버헤드 최소화
2. **Memory Leak**: Store 참조 시 적절한 cleanup
3. **Error Boundary**: React Error Boundary와의 연동 고려
4. **SSR Compatibility**: Next.js SSR에서의 동작 확인
5. **UX Consistency**: Header 에러와 GlobalNotification이 동시에 나타나지 않도록 보장
