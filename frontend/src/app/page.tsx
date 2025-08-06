"use client";
import React, { useEffect, useRef, useState } from 'react';
import Header from '../components/Header';
import ChatInput from '../components/ChatInput';
import ChatMessage from '../components/ChatMessage';
import WelcomeScreen from '../components/WelcomeScreen';
import LimitReachedModal from '../components/LimitReachedModal';
import { useChatStore } from '../stores/useChatStore';
import { useChat } from '../hooks/useChat';
import { useConversationRestore } from '../hooks/useConversationRestore';
import { useSession } from '../hooks/useSession';
import { useAuth } from '../hooks/useAuth';

export default function Home() {
  const { messages, error, isRestoring } = useChatStore();
  const { sendMessage } = useChat();
  const { restoreConversations } = useConversationRestore();
  const { isClient } = useSession();
  const { isAuthenticated, isUsageLimitReached, remainingUsage, dailyLimit } = useAuth();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showLimitModal, setShowLimitModal] = useState(false);

  // 클라이언트가 준비되고 세션이 설정된 후 대화 복원
  useEffect(() => {
    if (isClient) {
      console.log('🔄 클라이언트 준비 완료, 대화 복원 시작');
      restoreConversations();
    }
  }, [isClient, restoreConversations]);

  // 제한 도달 시 모달 자동 표시 (한 번만)
  useEffect(() => {
    if (!isAuthenticated && isUsageLimitReached && !showLimitModal) {
      // 메시지가 있는 상태에서만 모달 표시 (첫 로드 시에는 표시하지 않음)
      if (messages.length > 0) {
        setShowLimitModal(true);
      }
    }
  }, [isAuthenticated, isUsageLimitReached, messages.length, showLimitModal]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSampleQuestionClick = (question: string) => {
    // 제한 도달 시 모달 표시
    if (!isAuthenticated && isUsageLimitReached) {
      setShowLimitModal(true);
      return;
    }
    sendMessage(question);
  };

  return (
    <>
      <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white shadow-xl">
        <Header />
        <main ref={scrollRef} className="flex-1 overflow-y-auto conversation-container">
          <div id="conversationArea" className="min-h-full p-6">
            {isRestoring && (
              <div className="text-center py-4">
                <div className="inline-flex items-center space-x-2 text-gray-600">
                  <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-sm">이전 대화를 복원하는 중...</span>
                </div>
              </div>
            )}
            {messages.length === 0 && !isRestoring ? (
              <WelcomeScreen onSampleQuestionClick={handleSampleQuestionClick} />
            ) : (
              messages.map((msg) => <ChatMessage key={msg.id} msg={msg} />)
            )}
            {error && (
              <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md" role="alert">
                <p className="font-bold">Error</p>
                <p>{error}</p>
              </div>
            )}
          </div>
        </main>
        <ChatInput />
      </div>

      {/* 제한 도달 모달 */}
      <LimitReachedModal
        isOpen={showLimitModal}
        onClose={() => setShowLimitModal(false)}
        remainingUsage={remainingUsage}
        dailyLimit={dailyLimit}
      />
    </>
  );
}