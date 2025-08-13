import { useEffect, useCallback } from 'react';
import Cookies from 'js-cookie';
import { useAuthStore } from '../stores/useAuthStore';
import { useSession } from './useSession';
import api from '../lib/api'; // 수정: axios 대신 api 클라이언트 import
import { isAxiosError } from 'axios';

// AuthVerificationManager 클래스는 기존과 동일하게 유지...
class AuthVerificationManager {
  private static instance: AuthVerificationManager;
  private isVerifying = false;
  private hasInitialized = false;
  private verificationPromise: Promise<void> | null = null;
  private lastVerification = 0;
  private readonly VERIFICATION_COOLDOWN = 5000;

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
  setVerifying(status: boolean): void { this.isVerifying = status; if (status) { this.lastVerification = Date.now(); } }
  setInitialized(status: boolean): void { this.hasInitialized = status; }
  isInitialized(): boolean { return this.hasInitialized; }
  setPromise(promise: Promise<void> | null): void { this.verificationPromise = promise; }
  getPromise(): Promise<void> | null { return this.verificationPromise; }
  reset(): void { this.isVerifying = false; this.hasInitialized = false; this.verificationPromise = null; this.lastVerification = 0; }
}


export const useAuth = () => {
  const { 
    user, 
    isAuthenticated, 
    isLoading, 
    setUser, 
    setLoading, 
    setWhitelistError,
    logout 
  } = useAuthStore();
  const { sessionId } = useSession();
  const authManager = AuthVerificationManager.getInstance();

  const getToken = () => Cookies.get('access_token');
  const setToken = (token: string) => Cookies.set('access_token', token, { expires: 1 });
  const removeToken = () => Cookies.remove('access_token');

  const verifyAuth = useCallback(async (): Promise<void> => {
    if (authManager.isInitialized() || !authManager.canVerify()) {
      return authManager.getPromise() || Promise.resolve();
    }

    const token = getToken();
    if (!token) {
      setUser(null);
      authManager.setInitialized(true);
      setLoading(false);
      return;
    }

    authManager.setVerifying(true);
    setLoading(true);

    const verificationPromise = (async () => {
      try {
        // 수정: axios.get -> api.get
        const response = await api.get('/api/auth/verify');
        
        if (response.data.authenticated) {
          setUser(response.data.user);
        } else {
          setUser(null);
        }
        authManager.setInitialized(true);
      } catch (error) {
        console.error('❌ 인증 확인 실패:', error);
        setUser(null);
        removeToken();
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

  const loginWithGoogle = useCallback(async (credential: string) => {
    try {
      setLoading(true);
      const requestData: { id_token: string; session_id?: string } = {
        id_token: credential
      };
      
      if (sessionId && sessionId !== 'temp_session') {
        requestData.session_id = sessionId;
      }
      
      // 수정: axios.post -> api.post
      const response = await api.post('/api/auth/google-login', requestData);
      
      if (response.status === 200 && response.data.success) {
        setToken(response.data.access_token);
        setUser(response.data.user);
        authManager.setInitialized(true);
        
        console.log('✅ 로그인 성공, 페이지를 새로고침합니다.');
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
  }, [sessionId, setToken, setUser, setLoading, setWhitelistError]);

  const handleLogout = useCallback(async () => {
    try {
      const token = getToken();
      if (token) {
        // 수정: axios.post -> api.post
        await api.post('/api/auth/logout');
      }
    } catch (error) {
      console.error('❌ 로그아웃 API 호출 오류:', error);
    } finally {
      removeToken();
      logout();
      authManager.reset();
      window.location.reload();
    }
  }, [logout, removeToken]);

  useEffect(() => {
    if (!authManager.isInitialized()) {
      verifyAuth();
    }
  }, [verifyAuth]);

  return {
    user,
    isAuthenticated,
    isLoading,
    loginWithGoogle,
    logout: handleLogout,
    verifyAuth
  };
};
