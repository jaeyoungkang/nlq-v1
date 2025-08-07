// File: frontend/components/ChatInput.tsx
import React, { useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { useChat } from '../hooks/useChat';
import { useChatStore } from '../stores/useChatStore';
import { useAuth } from '../hooks/useAuth';

const SendIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0L16 8L8 16L7 15L13 9H0V7H13L7 1L8 0Z"/>
    </svg>
);

const ChatInput = () => {
  const [input, setInput] = useState('');
  const { sendMessage } = useChat();
  const { isLoading } = useChatStore();
  const { isAuthenticated } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      return; // 비인증 사용자는 전송 방지
    }
    sendMessage(input);
    setInput('');
  };

  // 비인증 사용자든 인증된 사용자든 동일한 입력창 표시 (비활성화만 다름)
  return (
    <div className="p-4 border-t border-gray-200 bg-white flex-shrink-0">
      <form onSubmit={handleSubmit} className="w-full">
        <div className={`flex items-end gap-3 p-3 border rounded-xl transition ${
          isAuthenticated 
            ? 'bg-gray-50 border-gray-300 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500' 
            : 'bg-gray-100 border-gray-200'
        }`}>
          <textarea
            id="messageInput"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && isAuthenticated) {
                    e.preventDefault();
                    handleSubmit(e);
                }
            }}
            placeholder={isAuthenticated ? "메시지를 입력하세요..." : "로그인 후 이용 가능합니다"}
            rows={1}
            className={`flex-1 bg-transparent border-none outline-none text-sm resize-none max-h-32 ${
              isAuthenticated ? 'placeholder-gray-400' : 'placeholder-gray-500 cursor-not-allowed'
            }`}
            disabled={isLoading || !isAuthenticated}
          />
          <button
            type="submit"
            className={`w-8 h-8 rounded-lg transition flex items-center justify-center flex-shrink-0 ${
              isAuthenticated && !isLoading && input.trim()
                ? 'bg-primary-500 text-white hover:bg-primary-600'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
            disabled={isLoading || !input.trim() || !isAuthenticated}
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