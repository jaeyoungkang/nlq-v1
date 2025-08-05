// File: frontend/hooks/useChat.ts
// 역할: 채팅 관련 로직 처리 (Custom Hook)
// API 서버와 통신하고, Zustand 스토어의 상태를 업데이트합니다.

import axios from 'axios';
import { useChatStore } from '../stores/useChatStore';

// 백엔드 API 서버 주소
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const useChat = () => {
  const { addMessage, setLoading, setError, updateLastMessage } = useChatStore();

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim()) return;

    // 1. 사용자 메시지를 스토어에 추가
    addMessage({ type: 'user', content: messageText });
    setLoading(true);

    // 2. AI 응답 대기용 메시지(플레이스홀더) 추가
    addMessage({ type: 'assistant', content: 'Thinking...' });

    try {
      // 3. 백엔드 API에 메시지 전송
      const response = await axios.post(`${API_URL}/api/chat`, {
        message: messageText,
      });

      if (response.data.success) {
        const result = response.data.result;
        // 4. 성공 시, 플레이스홀더를 실제 응답으로 업데이트
        updateLastMessage({
          content: "Query processed successfully. Here are the results:",
          sql: result.generated_sql,
          data: result.data,
        });
      } else {
        // API가 success: false를 반환한 경우
        throw new Error(response.data.error || 'An unknown API error occurred.');
      }
    } catch (err: any) {
      // 5. 에러 발생 시, 에러 메시지로 업데이트
      const errorMessage = err.response?.data?.error || err.message || 'Failed to connect to the server.';
      setError(errorMessage);
      updateLastMessage({
        content: `Sorry, an error occurred: ${errorMessage}`,
      });
    } finally {
      setLoading(false);
    }
  };

  return { sendMessage };
};