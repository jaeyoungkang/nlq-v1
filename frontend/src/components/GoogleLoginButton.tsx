// File: components/GoogleLoginButton.tsx
'use client';

import { useEffect, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';

// Google API의 Credential 응답에 대한 인터페이스 정의
interface CredentialResponse {
  credential: string;
}

// 전역 window 객체에 google 속성의 타입을 구체적으로 선언
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string | undefined;
            callback: (response: CredentialResponse) => void;
          }) => void;
          renderButton: (
            parent: HTMLDivElement,
            options: {
              theme: string;
              size: string;
              width: number;
              text: string;
              shape: string;
            }
          ) => void;
        };
      };
    };
  }
}

const GoogleLoginButton = () => {
  const { loginWithGoogle } = useAuth();
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // window.google 객체가 이미 로드되었는지 확인
    if (window.google?.accounts?.id) {
      initializeGoogleSignIn();
    } else {
      // Google SDK가 로드될 때까지 100ms 간격으로 확인
      const checkGoogle = setInterval(() => {
        if (window.google?.accounts?.id) {
          initializeGoogleSignIn();
          clearInterval(checkGoogle);
        }
      }, 100);

      // 컴포넌트 언마운트 시 인터벌 정리
      return () => clearInterval(checkGoogle);
    }
  }, []); // 의존성 배열이 비어 있으므로 컴포넌트 마운트 시 한 번만 실행

  const initializeGoogleSignIn = () => {
    // 이 함수는 window.google.accounts.id가 존재할 때만 호출됨을 보장
    if (!window.google?.accounts?.id) return;

    window.google.accounts.id.initialize({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
      callback: handleCredentialResponse,
    });

    if (buttonRef.current) {
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        width: 280,
        text: 'signin_with',
        shape: 'rectangular',
      });
    }
  };

  // handleCredentialResponse의 파라미터 타입을 CredentialResponse로 명확하게 지정
  const handleCredentialResponse = (response: CredentialResponse) => {
    // credential 속성이 존재하는지 확인 후 사용
    if (response.credential) {
        loginWithGoogle(response.credential);
    } else {
        console.error("Google credential not found.");
    }
  };

  return <div ref={buttonRef} className="google-signin-button"></div>;
};

export default GoogleLoginButton;
