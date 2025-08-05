// File: frontend/stores/useChatStore.ts
// 역할: 채팅 상태 관리 (Zustand 사용)
// 모든 메시지, 로딩 상태, 에러를 중앙에서 관리합니다.

import { create } from 'zustand';

// 메시지 객체의 타입 정의
export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sql?: string; // 생성된 SQL 쿼리 저장
  // FIX: `any` 대신 `Record<string, unknown>[]`를 사용하여 구체적인 타입을 명시
  // 이는 '키는 문자열이고 값은 모든 타입이 올 수 있는 객체들의 배열'을 의미합니다.
  data?: Record<string, unknown>[];   // 쿼리 결과 데이터 저장
}

// 스토어의 상태 및 액션 타입 정의
interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  addMessage: (message: Omit<Message, 'id'>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  updateLastMessage: (partialMessage: Partial<Message>) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  error: null,
  // 새 메시지를 메시지 목록에 추가하는 액션
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, { ...message, id: `msg-${Date.now()}-${Math.random()}` }],
      
    })),
  // 로딩 상태를 설정하는 액션
  setLoading: (loading) => set({ isLoading: loading, error: null }),
  // 에러 상태를 설정하는 액션
  setError: (error) => set({ error, isLoading: false }),
  // 마지막 메시지(주로 AI 응답)를 업데이트하는 액션
  updateLastMessage: (partialMessage) => {
    set((state) => {
      if (state.messages.length === 0) return state;
      const updatedMessages = [...state.messages];
      const lastMessageIndex = updatedMessages.length - 1;
      updatedMessages[lastMessageIndex] = {
        ...updatedMessages[lastMessageIndex],
        ...partialMessage,
      };
      return { messages: updatedMessages };
    });
  },
}));