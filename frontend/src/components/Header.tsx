'use client';

import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import GoogleLoginButton from './GoogleLoginButton';
import UserProfile from './UserProfile';
import LimitReachedModal from './LimitReachedModal';

const Header = () => {
  const { 
    isAuthenticated, 
    isLoading, 
    remainingUsage, 
    dailyLimit, 
    isUsageLimitReached 
  } = useAuth();
  
  const [showLimitModal, setShowLimitModal] = useState(false);

  // 사용량에 따른 스타일 결정
  const getUsageStyle = () => {
    if (isAuthenticated) return '';
    
    if (remainingUsage <= 0) {
      return 'bg-red-50 border-red-200 text-red-800';
    } else {
      return 'bg-primary-50 border-primary-200 text-primary-700';
    }
  };

  // 사용량에 따른 메시지 결정
  const getUsageMessage = () => {
    if (isAuthenticated) return '';
    
    if (remainingUsage <= 0) {
      return '비로그인 세션 사용량이 모두 소진되었습니다. 로그인하시면 세션이 계속 유지 됩니다.';
    } else if (remainingUsage <= 1) {
      return `비로그인 세션 사용중... ⚠️ ${remainingUsage} / ${dailyLimit}회 채팅 가능합니다. 로그인하시면 세션이 계속 유지 됩니다.`;
    } else if (remainingUsage <= 2) {
      return `비로그인 세션 사용중... ${remainingUsage} / ${dailyLimit}회 채팅 가능합니다. 로그인하시면 세션이 계속 유지 됩니다.`;
    } else {
      return `비로그인 세션 사용중... ${remainingUsage} / ${dailyLimit}회 채팅 가능합니다.`;
    }
  };

  return (
    <>
      <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-3xl font-bold text-primary-700">BigQuery AI Assistant</h1>
          
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
        
        {/* 사용량 안내 (비인증 사용자만) */}
        {!isAuthenticated && !isLoading && (
          <div className={`mt-3 px-4 py-3 border rounded-lg ${getUsageStyle()}`}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                {getUsageMessage()}
              </p>
              
              {/* 제한 도달 시 모달 열기 버튼 */}
              {isUsageLimitReached && (
                <button
                  onClick={() => setShowLimitModal(true)}
                  className="text-sm bg-red-600 text-white px-3 py-1 rounded-lg hover:bg-red-700 transition ml-3"
                >
                  자세히 보기
                </button>
              )}
            </div>
          </div>
        )}
      </header>

      {/* 제한 도달 모달 */}
      <LimitReachedModal
        isOpen={showLimitModal}
        onClose={() => setShowLimitModal(false)}
        remainingUsage={remainingUsage}
        dailyLimit={dailyLimit}
      />
    </>
  );
};

export default Header;