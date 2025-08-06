// hooks/useSession.ts
import { useEffect, useState } from 'react';

const SESSION_STORAGE_KEY = 'chat_session_id';

export const useSession = () => {
  const [sessionId, setSessionIdState] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);

  // 세션 ID 생성 함수
  const generateSessionId = (): string => {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 15);
    return `session_${timestamp}_${random}`;
  };

  // 세션 ID 유효성 검증
  const isValidSessionId = (id: string | null): boolean => {
    return !!(id && id.length > 10 && id.startsWith('session_') && id !== 'temp_session');
  };

  // 클라이언트 사이드인지 확인 및 세션 ID 초기화
  useEffect(() => {
    setIsClient(true);
    
    // localStorage에서 세션 ID 확인
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    
    if (storedSessionId && isValidSessionId(storedSessionId)) {
      setSessionIdState(storedSessionId);
      console.log('🔄 기존 세션 ID 복원:', storedSessionId);
    } else {
      // 새 세션 ID 생성
      const newSessionId = generateSessionId();
      localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
      setSessionIdState(newSessionId);
      console.log('🆕 새 세션 ID 생성:', newSessionId);
    }
  }, []);

  // 세션 ID 가져오기
  const getSessionId = (): string => {
    if (sessionId) {
      return sessionId;
    }
    
    if (!isClient) {
      return 'temp_session';
    }

    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (storedSessionId && isValidSessionId(storedSessionId)) {
      return storedSessionId;
    }

    const newSessionId = generateSessionId();
    localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
    setSessionIdState(newSessionId);
    return newSessionId;
  };

  // 세션 ID 설정
  const setSessionId = (newSessionId: string) => {
    if (isClient) {
      localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
    }
    setSessionIdState(newSessionId);
  };

  // 세션 초기화
  const clearSession = () => {
    if (isClient) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
    setSessionIdState(null);
  };

  return {
    sessionId,
    getSessionId,
    setSessionId,
    clearSession,
    generateSessionId,
    isValidSessionId,
    isClient
  };
};