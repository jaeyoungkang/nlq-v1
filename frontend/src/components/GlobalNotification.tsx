// frontend/src/components/GlobalNotification.tsx

'use client';

import React, { useEffect } from 'react';
import { useNotificationStore } from '../stores/useNotificationStore';

const GlobalNotification = () => {
  const { message, type, clearMessage } = useNotificationStore();

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => {
        clearMessage();
      }, 5000); // 5초 후 자동으로 닫힘
      return () => clearTimeout(timer);
    }
  }, [message, clearMessage]);

  if (!message) return null;

  const baseStyle = 'fixed top-5 right-5 z-50 p-4 rounded-lg shadow-lg text-white text-sm animate-fade-in-down';
  const typeStyles = {
    error: 'bg-red-500',
    success: 'bg-green-500',
    info: 'bg-blue-500',
  };

  return (
    <div className={`${baseStyle} ${typeStyles[type]}`}>
      <div className="flex justify-between items-center">
        <span>{message}</span>
        <button onClick={clearMessage} className="ml-4 font-bold">X</button>
      </div>
    </div>
  );
};

export default GlobalNotification;