'use client';

import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { useAuthStore } from '../stores/useAuthStore';
import GoogleLoginButton from './GoogleLoginButton';
import UserProfile from './UserProfile';

const Header = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { remainingUsage } = useAuthStore();

  return (
    <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-3xl font-bold gemini-gradient-text">BigQuery AI Assistant</h1>
        
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
      
      <p className="text-sm text-gray-600">자연어로 BigQuery 데이터를 조회하세요</p>
      
      {!isAuthenticated && remainingUsage < 10 && (
        <div className="mt-3 px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            오늘 {remainingUsage}회 더 이용 가능합니다. 
            <span className="font-semibold"> 무제한 이용을 원하시면 로그인하세요!</span>
          </p>
        </div>
      )}
    </header>
  );
};

export default Header;