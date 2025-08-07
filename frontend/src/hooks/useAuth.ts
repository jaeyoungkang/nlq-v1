import { useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import Cookies from 'js-cookie';
import { useAuthStore } from '../stores/useAuthStore';
import { useSession } from './useSession';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// 전역 싱글톤으로 인증 상태 관리
class AuthVerificationManager {
  private static instance: AuthVerificationManager;
  private isVerifying = false;
  private hasInitialized = false;
  private verificationPromise: Promise<void> | null = null;
  private lastVerification = 0;
  private readonly VERIFICATION_COOLDOWN = 5000; // 5초 쿨다운

  static getInstance(): AuthVerificationManager {
    if (!AuthVerificationManager.instance) {
      AuthVerificationManager.instance = new AuthVerificationManager();
    }
    return AuthVerificationManager.instance;
  }

  canVerify(): boolean {
    const now = Date.now();
    return !this.isVerifying && 
           !this.hasInitialized && 
           (now - this.lastVerification) > this.VERIFICATION_COOLDOWN;
  }

  setVerifying(status: boolean): void {
    this.isVerifying = status;
    if (status) {
      this.lastVerification = Date.now();
    }
  }

  setInitialized(status: boolean): void {
    this.hasInitialized = status;
  }

  isInitialized(): boolean {
    return this.hasInitialized;
  }

  setPromise(promise: Promise<void> | null): void {
    this.verificationPromise = promise;
  }

  getPromise(): Promise<void> | null {
    return this.verificationPromise;
  }

  reset(): void {
    this.isVerifying = false;
    this.hasInitialized = false;
    this.verificationPromise = null;
    this.lastVerification = 0;
  }
}

export const useAuth = () => {
  const { 
    user, 
    isAuthenticated, 
    isLoading, 
    setUser, 
    setLoading, 
    logout 
  } = useAuthStore();
  const { sessionId } = useSession();
  const interceptorId = useRef<number | null>(null);
  const authManager = AuthVerificationManager.getInstance();

  // JWT 토큰 관리
  const getToken = () => Cookies.get('access_token');
  const setToken = (token: string) => Cookies.set('access_token', token, { expires: 1 });
  const removeToken = () => Cookies.remove('access_token');

  // API 요청 인터셉터 설정 (한 번만)
  useEffect(() => {
    if (interceptorId.current !== null) {
      return; // 이미 설정됨
    }

    interceptorId.current = axios.interceptors.request.use((config) => {
      const token = getToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    return () => {
      if (interceptorId.current !== null) {
        axios.interceptors.request.eject(interceptorId.current);
        interceptorId.current = null;
      }
    };
  }, []); // 빈 의존성 배열

  // 인증 상태 확인 (수정된 버전)
  const verifyAuth = useCallback(async (): Promise<void> => {
    // 이미 초기화된 경우 건너뛰기
    if (authManager.isInitialized()) {
      console.log('✅ 인증 상태가 이미 초기화되었습니다');
      return;
    }

    // 검증 불가능한 상태 (쿨다운, 진행중 등)
    if (!authManager.canVerify()) {
      console.log('⏳ 인증 확인이 진행 중이거나 쿨다운 중입니다');
      
      // 진행 중인 Promise가 있으면 기다림
      const existingPromise = authManager.getPromise();
      if (existingPromise) {
        return existingPromise;
      }
      return;
    }

    // 토큰이 없으면 비인증 상태로 즉시 처리
    const token = getToken();
    if (!token) {
      console.log('🔓 토큰이 없습니다 - 비인증 상태로 설정');
      setUser(null);
      authManager.setInitialized(true);
      setLoading(false);
      return;
    }

    console.log('🔍 토큰이 있습니다 - 인증 상태 확인 시작');
    authManager.setVerifying(true);
    setLoading(true);

    const verificationPromise = (async () => {
      try {
        const response = await axios.get(`${API_URL}/api/auth/verify`);
        
        if (response.data.authenticated) {
          setUser(response.data.user);
          console.log('✅ 인증된 사용자:', response.data.user.email);
        } else {
          setUser(null);
          console.log('❌ 인증되지 않은 사용자 - 로그인 필요');
        }

        authManager.setInitialized(true);
        console.log('✅ 인증 상태 초기화 완료');
      } catch (error) {
        console.error('❌ 인증 확인 실패:', error);
        
        // 401 오류는 정상적인 비인증 상태로 처리
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          console.log('🔓 401 오류 - 인증되지 않은 상태로 처리');
          setUser(null);
          removeToken(); // 유효하지 않은 토큰 제거
        } else {
          // 다른 오류는 네트워크 문제 등으로 간주
          console.error('🌐 네트워크 오류 또는 서버 오류:', error);
          setUser(null);
          removeToken();
        }
        
        // 오류 시에도 초기화 완료로 처리 (무한 루프 방지)
        authManager.setInitialized(true);
      } finally {
        setLoading(false);
        authManager.setVerifying(false);
        authManager.setPromise(null);
      }
    })();

    authManager.setPromise(verificationPromise);
    return verificationPromise;
  }, [setUser, setLoading, removeToken]);

  // Google 로그인 (로그인 필수 버전)
  const loginWithGoogle = useCallback(async (credential: string) => {
    try {
      setLoading(true);
      console.log('🔐 Google 로그인 시작');
      
      const requestData: { id_token: string; session_id?: string } = {
        id_token: credential
      };
      
      if (sessionId && sessionId !== 'temp_session') {
        requestData.session_id = sessionId;
        console.log('🔗 세션 ID 포함:', sessionId);
      }
      
      const response = await axios.post(`${API_URL}/api/auth/google-login`, requestData);
      
      if (response.status === 200 && response.data.success) {
        setToken(response.data.access_token);
        setUser(response.data.user);
        
        // 인증 완료 후 상태 리셋
        authManager.setInitialized(true);
        
        console.log('✅ 로그인 성공:', response.data.user.email);
        
        if (response.data.session_link?.success && response.data.session_link.updated_conversations > 0) {
          console.log(`✅ 이전 대화 ${response.data.session_link.updated_conversations}개 연결됨`);
          
          setTimeout(() => {
            alert(response.data.message);
          }, 500);
        }
        
        // 페이지 새로고침
        setTimeout(() => {
          if (getToken()) {
            window.location.reload();
          }
        }, 800);
      } else {
        throw new Error(response.data.error || '로그인 응답 오류');
      }
    } catch (error) {
      console.error('❌ Google 로그인 실패:', error);
      
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        const errorData = error.response.data;
        alert(`인증 실패: ${errorData?.error || '알 수 없는 오류'}`);
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId, setToken, setUser, setLoading, getToken]);

  // 로그아웃
  const handleLogout = useCallback(async () => {
    try {
      console.log('👋 로그아웃 시작');
      
      // 토큰이 있는 경우에만 로그아웃 API 호출
      const token = getToken();
      if (token) {
        await axios.post(`${API_URL}/api/auth/logout`);
      }
    } catch (error) {
      console.error('❌ 로그아웃 오류:', error);
      // 로그아웃 API 실패해도 계속 진행
    } finally {
      removeToken();
      logout();
      
      // 인증 관리자 리셋
      authManager.reset();
      
      console.log('🔄 로그아웃 완료, 페이지 새로고침');
      window.location.reload();
    }
  }, [logout, removeToken]);

  // 앱 시작 시 한 번만 인증 확인
  useEffect(() => {
    if (!authManager.isInitialized()) {
      verifyAuth();
    }
  }, []); // 완전히 빈 의존성 배열

  return {
    user,
    isAuthenticated,
    isLoading,
    loginWithGoogle,
    logout: handleLogout,
    verifyAuth
  };
};