// frontend/src/components/Header.tsx

'use client';

import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../stores/useAuthStore';
import GoogleLoginButton from './GoogleLoginButton';
import UserProfile from './UserProfile';
import { XMarkIcon, ExclamationCircleIcon } from '@heroicons/react/24/solid'


const Header = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { whitelistError, setWhitelistError } = useAuthStore();

  const handleCloseError = () => {
    setWhitelistError(null);
  };

  return (
    <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
      {whitelistError && (
        <div className={`mb-4 p-4 border rounded-lg ${
          whitelistError.reason === 'session_expired' 
          ? 'bg-blue-50 border-blue-200' 
          : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center">
                <ExclamationCircleIcon className={`w-5 h-5 mr-2 ${whitelistError.reason === 'session_expired' ? 'text-blue-400' : 'text-red-400' }`}
                />
                <h3 className={`text-sm font-medium ${whitelistError.reason === 'session_expired' ? 'text-blue-800' : 'text-red-800'}`}>
                  {whitelistError.reason === 'session_expired' ? '세션 만료' : '접근 권한 없음'}
                </h3>
              </div>
              <div className={`mt-2 text-sm ${whitelistError.reason === 'session_expired' ? 'text-blue-700' : 'text-red-700'}`}>
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
              className={`ml-3 inline-flex focus:outline-none ${whitelistError.reason === 'session_expired' ? 'text-blue-400 hover:text-blue-600' : 'text-red-400 hover:text-red-600'}`}
              onClick={handleCloseError}
            >
            <XMarkIcon className="w-5 h-5 text-gray-500" />
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