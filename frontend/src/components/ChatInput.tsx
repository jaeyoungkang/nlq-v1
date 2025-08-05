// File: frontend/components/ChatInput.tsx
import React, { useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { useChat } from '../hooks/useChat';
import { useChatStore } from '../stores/useChatStore';

const SendIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0L16 8L8 16L7 15L13 9H0V7H13L7 1L8 0Z"/>
    </svg>
);

const ChatInput = () => {
  const [input, setInput] = useState('');
  const { sendMessage } = useChat();
  const { isLoading } = useChatStore();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
    setInput('');
  };

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
            disabled={isLoading}
          />
          <button
            type="submit"
            className="bg-primary-500 text-white w-8 h-8 rounded-lg hover:bg-primary-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition flex items-center justify-center flex-shrink-0"
            disabled={isLoading || !input.trim()}
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