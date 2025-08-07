// File: frontend/hooks/useChat.ts
// 역할: 채팅 관련 로직 처리 (Custom Hook) - 로그인 필수 버전 + SSE 스트리밍
// API 서버와 통신하고, Zustand 스토어의 상태를 업데이트합니다.

import axios, { isAxiosError } from 'axios';
import { useChatStore } from '../stores/useChatStore';
import { useSession } from './useSession';
import Cookies from 'js-cookie';

// 백엔드 API 서버 주소
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// SSE 이벤트 타입 정의
interface SSEProgressEvent {
  stage: string;
  message: string;
}

interface SSEResultEvent {
  success: boolean;
  request_id: string;
  conversation_id: string;
  result: {
    type: string;
    content?: string;
    generated_sql?: string;
    data?: Record<string, unknown>[];
    row_count?: number;
  };
  performance: {
    execution_time_ms: number;
  };
  conversation_saved: boolean;
  user: {
    user_id: string;
    email: string;
  };
}

interface SSEErrorEvent {
  error: string;
  error_type: string;
}

export const useChat = () => {
  const { 
    addMessage, 
    setLoading, 
    setError, 
    updateLastMessage, 
    setStreaming 
  } = useChatStore();
  const { sessionId } = useSession();

  // SSE 스트리밍 방식으로 메시지 전송
  const sendMessageStream = async (messageText: string) => {
    if (!messageText.trim()) return;

    console.log('🚀 SSE 스트리밍 시작:', messageText);

    // 1. 사용자 메시지를 스토어에 추가
    addMessage({ type: 'user', content: messageText });
    setStreaming(true);

    // 2. 초기 대기 메시지는 추가하지 않음 (진행상황 메시지들이 대신 표시됨)

    try {
      const token = Cookies.get('access_token');
      if (!token) {
        throw new Error('인증 토큰이 없습니다. 로그인해주세요.');
      }

      // 3. SSE 연결 설정
      const requestData: { message: string; session_id?: string } = {
        message: messageText,
      };

      // 세션 ID가 유효하면 요청에 포함 (로그인 시 세션 연결용)
      if (sessionId && sessionId !== 'temp_session') {
        requestData.session_id = sessionId;
      }

      console.log('📡 SSE 요청 데이터:', requestData);

      // POST 요청으로 스트리밍 시작
      const response = await fetch(`${API_URL}/api/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(requestData),
      });

      console.log('📡 SSE 응답 상태:', response.status, response.statusText);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('응답 본문이 없습니다.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      console.log('📖 SSE 스트림 읽기 시작');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('📖 SSE 스트림 읽기 완료');
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        console.log('📨 수신된 청크:', chunk);

        // SSE 메시지 파싱 (\n\n으로 구분)
        const messages = buffer.split('\n\n');
        buffer = messages.pop() || ''; // 마지막 불완전한 메시지는 버퍼에 보관

        for (const message of messages) {
          if (!message.trim()) continue;

          console.log('🔍 파싱할 SSE 메시지:', message);

          const lines = message.split('\n');
          let eventType = '';
          let data = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.substring(6).trim();
            } else if (line.startsWith('data:')) {
              data = line.substring(5).trim();
            }
          }

          if (!data) continue;

          console.log('🔍 파싱된 데이터:', data, '이벤트 타입:', eventType);

          try {
            const parsedData = JSON.parse(data);
            console.log('✅ JSON 파싱 성공:', parsedData);

            // 이벤트 타입별 처리
            if (eventType === 'progress' || parsedData.stage) {
              // 진행상황 이벤트 - 별도 메시지로 추가
              const progressEvent = parsedData as SSEProgressEvent;
              console.log('📈 진행상황 메시지 추가:', progressEvent.message);
              addMessage({
                type: 'assistant',
                content: progressEvent.message,
                isProgress: true
              });
            } else if (eventType === 'result' || parsedData.success !== undefined) {
              // 최종 결과 이벤트 - 별도 메시지로 추가
              const resultEvent = parsedData as SSEResultEvent;
              console.log('🎯 최종 결과 메시지 추가:', resultEvent);
              
              if (resultEvent.success) {
                const result = resultEvent.result;
                
                // 최종 결과 전에 잠시 지연 (완료 메시지 표시 시간 확보)
                await new Promise(resolve => setTimeout(resolve, 300));
                
                // 응답 타입별 처리
                if (result.type === 'query_result') {
                  // SQL 쿼리 결과
                  addMessage({
                    type: 'assistant',
                    content: "Query processed successfully. Here are the results:",
                    sql: result.generated_sql,
                    data: result.data,
                    isProgress: false
                  });
                } else if (['guide_result', 'analysis_result', 'metadata_result', 'out_of_scope_result'].includes(result.type)) {
                  // 가이드, 분석, 메타데이터, 범위 외 응답
                  const content = result.content || "응답을 생성했지만 내용이 비어있습니다.";
                  
                  addMessage({
                    type: 'assistant',
                    content: content,
                    sql: result.generated_sql || undefined,
                    data: result.data || undefined,
                    isProgress: false
                  });
                } else {
                  // 알 수 없는 타입의 경우 기본 처리
                  console.warn('⚠️ Unknown result type:', result.type);
                  addMessage({
                    type: 'assistant',
                    content: result.content || JSON.stringify(result, null, 2),
                    sql: result.generated_sql || undefined,
                    data: result.data || undefined,
                    isProgress: false
                  });
                }
              }
            } else if (eventType === 'error' || parsedData.error) {
              // 에러 이벤트
              const errorEvent = parsedData as SSEErrorEvent;
              throw new Error(errorEvent.error);
            }
          } catch (parseError) {
            console.error('❌ SSE 데이터 파싱 오류:', parseError, '원본 데이터:', data);
          }
        }
      }

      console.log('✅ SSE 스트리밍 완료');

    } catch (err: unknown) {
      // 에러 발생 시, 에러 메시지로 업데이트
      let errorMessage = 'Failed to connect to the server.';

      if (isAxiosError(err)) {
        errorMessage = err.response?.data?.error || err.message;
        
        if (err.response?.status === 401) {
          errorMessage = '로그인이 필요합니다. 페이지를 새로고침하고 다시 로그인해주세요.';
        }
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      console.error('❌ SSE Chat error:', errorMessage);
      setError(errorMessage);
      addMessage({
        type: 'assistant',
        content: `Sorry, an error occurred: ${errorMessage}`,
        isProgress: false
      });
    } finally {
      setStreaming(false);
    }
  };

  // 기존 HTTP 방식 메시지 전송 (유지)
  const sendMessage = async (messageText: string) => {
    if (!messageText.trim()) return;

    // 1. 사용자 메시지를 스토어에 추가
    addMessage({ type: 'user', content: messageText });
    setLoading(true);

    // 2. AI 응답 대기용 메시지(플레이스홀더) 추가
    addMessage({ type: 'assistant', content: 'Thinking...' });

    try {
      // 3. 백엔드 API에 메시지 전송 (세션 ID 포함 - 로그인 연결용)
      const requestData: { message: string; session_id?: string } = {
        message: messageText,
      };

      // 세션 ID가 유효하면 요청에 포함 (로그인 시 세션 연결용)
      if (sessionId && sessionId !== 'temp_session') {
        requestData.session_id = sessionId;
      }

      const response = await axios.post(`${API_URL}/api/chat`, requestData);

      console.log('🔍 Backend response:', response.data);

      if (response.data.success) {
        const result = response.data.result;
        
        // 4. 응답 타입에 따른 처리
        console.log('🔍 Result type:', result.type);
        console.log('🔍 Result content:', result.content);
        
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
          console.log('🔍 Updating message with content:', content);
          
          updateLastMessage({
            content: content,
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
      // 5. 에러 발생 시, 에러 메시지로 업데이트
      let errorMessage = 'Failed to connect to the server.';

      if (isAxiosError(err)) {
        errorMessage = err.response?.data?.error || err.message;
        
        if (err.response?.status === 401) {
          errorMessage = '로그인이 필요합니다. 페이지를 새로고침하고 다시 로그인해주세요.';
        }
        
        if (err.response?.data) {
          console.error('🔍 Error response data:', err.response.data);
        }
      } else if (err instanceof Error) {
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

  return { 
    sendMessage, // 기존 HTTP 방식
    sendMessageStream // 새로운 SSE 스트리밍 방식
  };
};