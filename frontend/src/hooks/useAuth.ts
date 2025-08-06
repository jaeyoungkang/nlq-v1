import { useEffect } from 'react';
import axios from 'axios';
import Cookies from 'js-cookie';
import { useAuthStore } from '../stores/useAuthStore';
import { useSession } from './useSession';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const useAuth = () => {
  const { user, isAuthenticated, isLoading, setUser, setLoading, logout } = useAuthStore();
  const { sessionId } = useSession();

  // JWT 토큰 관리
  const getToken = () => Cookies.get('access_token');
  const setToken = (token: string) => Cookies.set('access_token', token, { expires: 1 });
  const removeToken = () => Cookies.remove('access_token');

  // API 요청 인터셉터 설정
  useEffect(() => {
    axios.interceptors.request.use((config) => {
      const token = getToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }, []);

  // 인증 상태 확인
  const verifyAuth = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/auth/verify`);
      if (response.data.authenticated) {
        setUser(response.data.user);
      } else {
        setUser(null);
      }
    } catch (error) {
      setUser(null);
      removeToken();
    } finally {
      setLoading(false);
    }
  };

  // Google 로그인 (세션 ID 포함)
  const loginWithGoogle = async (credential: string) => {
    try {
      setLoading(true);
      
      // 요청 데이터에 세션 ID 포함
      const requestData: { id_token: string; session_id?: string } = {
        id_token: credential
      };
      
      // 유효한 세션 ID가 있으면 포함
      if (sessionId && sessionId !== 'temp_session') {
        requestData.session_id = sessionId;
        console.log('🔗 로그인 시 세션 ID 전달:', sessionId);
      }
      
      const response = await axios.post(`${API_URL}/api/auth/google-login`, requestData);
      
      if (response.data.success) {
        setToken(response.data.access_token);
        setUser(response.data.user);
        
        // 세션 연결 결과 처리
        if (response.data.session_link?.success && response.data.session_link.updated_conversations > 0) {
          console.log(`✅ 이전 대화 ${response.data.session_link.updated_conversations}개가 계정에 연결되었습니다`);
          
          // 사용자에게 알림 (선택사항)
          if (typeof window !== 'undefined') {
            setTimeout(() => {
              alert(response.data.message);
            }, 1000);
          }
        }
        
        // 로그인 성공 후 페이지 새로고침으로 복원 플래그 리셋
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      }
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      setLoading(false);
    }
  };

  // 로그아웃
  const handleLogout = async () => {
    try {
      await axios.post(`${API_URL}/api/auth/logout`);
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      removeToken();
      logout();
      // 로그아웃 후 페이지 새로고침
      window.location.reload();
    }
  };

  // 앱 시작 시 인증 상태 확인
  useEffect(() => {
    verifyAuth();
  }, []);

  return {
    user,
    isAuthenticated,
    isLoading,
    loginWithGoogle,
    logout: handleLogout,
    verifyAuth
  };
};