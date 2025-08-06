// File: frontend/components/ChatInput.tsx
import React, { useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { useChat } from '../hooks/useChat';
import { useChatStore } from '../stores/useChatStore';
import { useAuth } from '../hooks/useAuth';
import GoogleLoginButton from './GoogleLoginButton';

const SendIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0L16 8L8 16L7 15L13 9H0V7H13L7 1L8 0Z"/>
    </svg>
);

const ChatInput = () => {
  const [input, setInput] = useState('');
  const { sendMessage } = useChat();
  const { isLoading } = useChatStore();
  const { isAuthenticated, isUsageLimitReached, remainingUsage } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isUsageLimitReached && !isAuthenticated) {
      return; // 제한 도달 시 전송 방지
    }
    sendMessage(input);
    setInput('');
  };

  // 제한 도달 시 표시할 컴포넌트
  if (isUsageLimitReached && !isAuthenticated) {
    return (
      <div className="p-4 border-t border-gray-200 bg-white flex-shrink-0">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
          <div className="text-red-600 text-sm font-semibold mb-2">
            🚫 일일 사용량이 모두 소진되었습니다
          </div>
          <p className="text-red-700 text-sm mb-4">
            로그인하시면 무제한으로 이용하실 수 있어요!
          </p>
          <div className="flex justify-center">
            <GoogleLoginButton />
          </div>
        </div>
      </div>
    );
  }

  // 일반 입력창
  return (
    <div className="p-4 border-t border-gray-200 bg-white flex-shrink-0">
      <form onSubmit={handleSubmit} className="w-full">
        <div className="flex items-end gap-3 p-3 bg-gray-50 border border-gray-300 rounded-xl focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500 transition">
          <textarea
            id="messageInput"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                }
            }}
            placeholder="메시지를 입력하세요..."
            rows={1}
            className="flex-1 bg-transparent border-none outline-none text-sm resize-none max-h-32 placeholder-gray-400"
            required
            disabled={isLoading || (isUsageLimitReached && !isAuthenticated)}
          />
          <button
            type="submit"
            className="bg-primary-500 text-white w-8 h-8 rounded-lg hover:bg-primary-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition flex items-center justify-center flex-shrink-0"
            disabled={isLoading || !input.trim() || (isUsageLimitReached && !isAuthenticated)}
            aria-label="메시지 전송"
          >
            {isLoading ? <LoaderCircle className="animate-spin" size={16} /> : <SendIcon />}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ChatInput;