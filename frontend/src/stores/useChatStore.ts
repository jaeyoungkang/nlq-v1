// File: frontend/stores/useChatStore.ts
// 역할: 채팅 상태 관리 (Zustand 사용) - SSE 진행상황 추가
// 모든 메시지, 로딩 상태, 에러를 중앙에서 관리합니다.

import { create } from 'zustand';

// 메시지 객체의 타입 정의
export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sql?: string; // 생성된 SQL 쿼리 저장
  data?: Record<string, unknown>[]; // 쿼리 결과 데이터 저장
  isProgress?: boolean; // 진행상황 메시지 여부
}

// 스토어의 상태 및 액션 타입 정의
interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  isRestoring: boolean;
  isStreaming: boolean; // SSE 스트리밍 상태
  addMessage: (message: Omit<Message, 'id'>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setRestoring: (restoring: boolean) => void;
  setStreaming: (streaming: boolean) => void; // SSE 스트리밍 상태 설정
  updateLastMessage: (partialMessage: Partial<Message>) => void;
  restoreMessages: (messages: Message[]) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  error: null,
  isRestoring: false,
  isStreaming: false,
  
  // 새 메시지를 메시지 목록에 추가하는 액션
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, { ...message, id: `msg-${Date.now()}-${Math.random()}` }],
    })),
    
  // 로딩 상태를 설정하는 액션
  setLoading: (loading) => set({ isLoading: loading, error: null }),
  
  // 에러 상태를 설정하는 액션
  setError: (error) => set({ error, isLoading: false }),
  
  // 복원 상태를 설정하는 액션
  setRestoring: (restoring) => set({ isRestoring: restoring }),
  
  // SSE 스트리밍 상태를 설정하는 액션
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  
  // 대화 복원을 위한 메시지 일괄 설정
  restoreMessages: (messages) => set({ messages }),
  
  // 메시지 초기화
  clearMessages: () => set({ messages: [] }),
  
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