// File: frontend/app/page.tsx
// (수정됨: 원본 HTML의 전체 레이아웃 클래스 적용)
"use client";
import React, { useEffect, useRef } from 'react';
import Header from '../components/Header';
import ChatInput from '../components/ChatInput';
import ChatMessage from '../components/ChatMessage';
import WelcomeScreen from '../components/WelcomeScreen';
import { useChatStore } from '../stores/useChatStore';
import { useChat } from '../hooks/useChat';

export default function Home() {
  const { messages, error } = useChatStore();
  const { sendMessage } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white shadow-xl">
      <Header />
      <main ref={scrollRef} className="flex-1 overflow-y-auto conversation-container">
        <div id="conversationArea" className="min-h-full p-6">
          {messages.length === 0 ? (
            <WelcomeScreen onSampleQuestionClick={sendMessage} />
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
  );
}