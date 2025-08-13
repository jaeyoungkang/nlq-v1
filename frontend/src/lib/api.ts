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

export default api;
