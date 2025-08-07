"use client";
import React, { useEffect, useRef } from 'react';
import Header from '../components/Header';
import ChatInput from '../components/ChatInput';
import ChatMessage from '../components/ChatMessage';
import WelcomeScreen from '../components/WelcomeScreen';
import { useChatStore } from '../stores/useChatStore';
import { useChat } from '../hooks/useChat';
import { useConversationRestore } from '../hooks/useConversationRestore';
import { useSession } from '../hooks/useSession';
import { useAuth } from '../hooks/useAuth';

export default function Home() {
  const { messages, error, isRestoring } = useChatStore();
  const { sendMessageStream } = useChat(); // SSE 스트리밍 방식 사용
  const { restoreConversations } = useConversationRestore();
  const { isClient } = useSession();
  const { isAuthenticated } = useAuth();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 클라이언트가 준비되고 세션이 설정된 후 대화 복원
  useEffect(() => {
    if (isClient) {
      console.log('🔄 클라이언트 준비 완료, 대화 복원 시작');
      restoreConversations();
    }
  }, [isClient, restoreConversations]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSampleQuestionClick = (question: string) => {
    // 인증된 사용자만 샘플 질문 사용 가능 (비인증 시 아무 동작 없음)
    if (isAuthenticated) {
      sendMessageStream(question); // SSE 스트리밍 방식으로 전송
    }
  };

  // 연속된 assistant 메시지에서 라벨 표시 여부 결정
  const shouldShowLabel = (currentIndex: number): boolean => {
    if (currentIndex === 0) return true; // 첫 번째 메시지는 항상 라벨 표시
    
    const currentMessage = messages[currentIndex];
    const previousMessage = messages[currentIndex - 1];
    
    // 현재 메시지가 user 타입이면 항상 라벨 표시
    if (currentMessage.type === 'user') return true;
    
    // 현재 메시지가 assistant이고 이전 메시지도 assistant이면 라벨 숨김
    if (currentMessage.type === 'assistant' && previousMessage.type === 'assistant') {
      return false;
    }
    
    // 그 외의 경우는 라벨 표시
    return true;
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white shadow-xl">
      <Header />
      <main ref={scrollRef} className="flex-1 overflow-y-auto conversation-container">
        <div id="conversationArea" className="min-h-full">
          {/* WelcomeScreen을 항상 첫 번째 요소로 표시 */}
          <div className="p-6 border-b border-gray-100">
            <WelcomeScreen onSampleQuestionClick={handleSampleQuestionClick} />
          </div>
          
          {/* 복원 상태 표시 */}
          {isRestoring && (
            <div className="text-center py-4 px-6">
              <div className="inline-flex items-center space-x-2 text-gray-600">
                <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-sm">이전 대화를 복원하는 중...</span>
              </div>
            </div>
          )}
          
          {/* 대화 메시지들 */}
          {messages.length > 0 && (
            <div className="px-6 pt-4">
              <div className="mb-4">
                <div className="text-sm font-semibold text-gray-500 mb-2 flex items-center">
                  <div className="flex-1 border-t border-gray-200"></div>
                  <span className="px-3 bg-white">대화 시작</span>
                  <div className="flex-1 border-t border-gray-200"></div>
                </div>
              </div>
              {messages.map((msg, index) => (
                <div key={msg.id} className="mb-6">
                  <ChatMessage 
                    msg={msg} 
                    showLabel={shouldShowLabel(index)}
                  />
                </div>
              ))}
            </div>
          )}
          
          {/* 에러 표시 */}
          {error && (
            <div className="px-6 pb-4">
              <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-md" role="alert">
                <p className="font-bold">Error</p>
                <p>{error}</p>
              </div>
            </div>
          )}
        </div>
      </main>
      <ChatInput />
    </div>
  );
}