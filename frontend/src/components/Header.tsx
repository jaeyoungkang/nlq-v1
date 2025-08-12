'use client';

import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../stores/useAuthStore';
import GoogleLoginButton from './GoogleLoginButton';
import UserProfile from './UserProfile';

const Header = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { whitelistError, setWhitelistError } = useAuthStore();

  const handleCloseError = () => {
    setWhitelistError(null);
  };

  return (
    <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
      {whitelistError && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center">
                <svg className="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <h3 className="text-sm font-medium text-red-800">접근 권한 없음</h3>
              </div>
              <div className="mt-2 text-sm text-red-700">
                <p>{whitelistError.message}</p>
                {whitelistError.reason === 'pending_approval' && (
                  <p className="mt-1 text-xs">관리자 승인 후 서비스를 이용하실 수 있습니다.</p>
                )}
                {whitelistError.reason === 'not_whitelisted' && (
                  <p className="mt-1 text-xs"> <a href='https://analytics.artificialmind.kr/'> https://analytics.artificialmind.kr/ </a> 에서 계정 등록을 요청하세요!</p>
                )}
              </div>
            </div>
            <button
              type="button"
              className="ml-3 inline-flex text-red-400 hover:text-red-600 focus:outline-none"
              onClick={handleCloseError}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      )}
      
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

export default Header;