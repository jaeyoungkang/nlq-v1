// File: frontend/hooks/useChat.ts
// 역할: 채팅 관련 로직 처리 (Custom Hook) - 응답 처리 개선
// API 서버와 통신하고, Zustand 스토어의 상태를 업데이트합니다.

import axios, { isAxiosError } from 'axios';
import { useChatStore } from '../stores/useChatStore';
import { useAuthStore } from '../stores/useAuthStore';

// 백엔드 API 서버 주소
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const useChat = () => {
  const { addMessage, setLoading, setError, updateLastMessage } = useChatStore();
  const { setRemainingUsage } = useAuthStore();

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

      console.log('🔍 Backend response:', response.data); // 디버깅 로그

      if (response.data.success) {
        const result = response.data.result;
        
        // 4. 사용량 정보 업데이트
        if (response.data.usage?.remaining !== undefined) {
          setRemainingUsage(response.data.usage.remaining);
        }
        
        // 5. 응답 타입에 따른 처리 개선
        console.log('🔍 Result type:', result.type); // 디버깅 로그
        console.log('🔍 Result content:', result.content); // 디버깅 로그
        
        // 응답 타입별 처리
        if (result.type === 'query_result') {
          // SQL 쿼리 결과
          updateLastMessage({
            content: "Query processed successfully. Here are the results:",
            sql: result.generated_sql,
            data: result.data,
          });
        } else if (result.type === 'guide_result' || result.type === 'analysis_result' || 
                   result.type === 'metadata_result' || result.type === 'out_of_scope_result') {
          // 가이드, 분석, 메타데이터, 범위 외 응답
          const content = result.content || "응답을 생성했지만 내용이 비어있습니다.";
          console.log('🔍 Updating message with content:', content); // 디버깅 로그
          
          updateLastMessage({
            content: content,
            // SQL과 데이터는 이 타입들에서는 보통 없음
            sql: result.generated_sql || undefined,
            data: result.data || undefined,
          });
        } else {
          // 알 수 없는 타입의 경우 기본 처리
          console.warn('⚠️ Unknown result type:', result.type);
          updateLastMessage({
            content: result.content || JSON.stringify(result, null, 2),
            sql: result.generated_sql || undefined,
            data: result.data || undefined,
          });
        }
      } else {
        // API가 success: false를 반환한 경우
        throw new Error(response.data.error || 'An unknown API error occurred.');
      }
    } catch (err: unknown) {
      // 6. 에러 발생 시, 에러 메시지로 업데이트
      let errorMessage = 'Failed to connect to the server.'; // 기본 에러 메시지

      if (isAxiosError(err)) {
        // Axios 에러인 경우, 서버에서 보낸 에러 메시지를 우선적으로 사용
        errorMessage = err.response?.data?.error || err.message;
        
        // 응답 데이터 로깅 (디버깅용)
        if (err.response?.data) {
          console.error('🔍 Error response data:', err.response.data);
        }
      } else if (err instanceof Error) {
        // 일반적인 Error 객체인 경우, 해당 에러 메시지 사용
        errorMessage = err.message;
      }

      console.error('❌ Chat error:', errorMessage);
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