import axios from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// 1. axios 인스턴스를 생성합니다.
const api = axios.create({
  baseURL: API_URL,
});

// 2. 요청 인터셉터(통제실)를 설정합니다.
//    이제 모든 요청은 이 코드를 거친 후에 서버로 전송됩니다.
api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token');
  if (token) {
    // 토큰이 있으면 항상 Authorization 헤더에 포함시킵니다.
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// 3. 응답 인터셉터 - 모든 에러를 자동 처리
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // 커스텀 헤더로 자동 처리 건너뛰기 가능
    if (error.config?.headers?.['X-Skip-Global-Error'] === 'true') {
      return Promise.reject(error);
    }

    // 동적 import로 circular dependency 방지
    const { useNotificationStore } = await import('../stores/useNotificationStore');
    const { useAuthStore } = await import('../stores/useAuthStore');
    
    const errorData = error.response?.data;
    
    // 자동 에러 처리
    handleErrorAutomatically(errorData, error.response?.status, useNotificationStore, useAuthStore);
    
    return Promise.reject(error);
  }
);

// 완전 자동화된 에러 핸들러
const handleErrorAutomatically = (errorData: unknown, status: number | undefined, useNotificationStore: typeof import('../stores/useNotificationStore').useNotificationStore, useAuthStore: typeof import('../stores/useAuthStore').useAuthStore) => {
  const { setMessage } = useNotificationStore.getState();
  const { setWhitelistError, logout } = useAuthStore.getState();
  
  if (!errorData || typeof errorData !== 'object') {
    // 네트워크 에러
    setMessage('네트워크 연결을 확인해주세요', 'error');
    return;
  }

  const error = errorData as { error_type?: string; error?: string; details?: { reason?: string; user_status?: string } };
  
  switch (error.error_type) {
    // 자동 로그아웃 + 알림
    case 'token_expired':
    case 'invalid_token':
      logout();
      setMessage('로그인이 만료되었습니다', 'info');
      // 페이지 새로고침을 지연시켜 사용자가 메시지를 볼 수 있게 함
      setTimeout(() => {
        window.location.reload();
      }, 1000);
      break;
      
    // Header 표시 (화이트리스트 에러만)
    case 'access_denied':
      // GlobalNotification 메시지가 있으면 제거 (중복 방지)
      setMessage('', 'info');
      setWhitelistError({
        message: error.error || '접근이 거부되었습니다',
        errorType: error.error_type || 'access_denied',
        reason: error.details?.reason,
        userStatus: error.details?.user_status
      });
      break;
      
    // GlobalNotification 표시 (모든 일반 에러)
    case 'validation_error':
    case 'service_error':
    case 'internal_error':
    case 'not_found':
      setMessage(error.error || '오류가 발생했습니다', 'error');
      break;
      
    default:
      // 상태 코드별 기본 처리
      if (status === 401) {
        logout();
        setMessage('인증이 필요합니다. 다시 로그인해주세요', 'info');
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else if (status && status >= 500) {
        setMessage('서버에 일시적인 문제가 발생했습니다', 'error');
      } else {
        setMessage(error.error || '오류가 발생했습니다', 'error');
      }
  }
};

// SSE 전용 헬퍼 함수
export const createSSERequest = (endpoint: string, options: RequestInit = {}) => {
  const token = Cookies.get('access_token');
  return fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options.headers,
    }
  });
};

export default api;
export { API_URL };
