'use client';

import React from 'react';
import { useAuth } from '../hooks/useAuth';
import GoogleLoginButton from './GoogleLoginButton';
import UserProfile from './UserProfile';

const Header = () => {
  const { isAuthenticated, isLoading } = useAuth();

  return (
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
    </header>
  );
};

export default Header;