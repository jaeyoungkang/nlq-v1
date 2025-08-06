import { useEffect } from 'react';
import axios from 'axios';
import Cookies from 'js-cookie';
import { useAuthStore } from '../stores/useAuthStore';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const useAuth = () => {
  const { user, isAuthenticated, isLoading, setUser, setLoading, logout } = useAuthStore();

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

  // Google 로그인
  const loginWithGoogle = async (credential: string) => {
    try {
      setLoading(true);
      const response = await axios.post(`${API_URL}/api/auth/google-login`, {
        id_token: credential
      });
      
      if (response.data.success) {
        setToken(response.data.access_token);
        setUser(response.data.user);
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