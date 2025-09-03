import { useCallback, useRef } from 'react';
import { useChatStore, Message } from '../stores/useChatStore';
import { useAuthStore } from '../stores/useAuthStore';
import api from '../lib/api';

// ... (인터페이스 정의는 기존과 동일)
interface ApiMessage {
  message_id: string;
  message: string;
  message_type: 'user' | 'assistant';
  timestamp: string;
  query_type: string | null;
  generated_sql: string | null;
  execution_time_ms: number | null;
  result_data?: Record<string, unknown>[];  // 백엔드와 일치하도록 수정
  result_row_count?: number;  // 백엔드와 일치하도록 수정
}

interface LatestConversationResponse {
  success: boolean;
  data?: {
    conversation: {
      messages: ApiMessage[];
      message_count: number;
    } | null;
  };
  conversation?: {
    messages: ApiMessage[];
    message_count: number;
  } | null;
  error?: string;
}


export const useConversationRestore = () => {
  const { restoreMessages, setRestoring } = useChatStore();
  const { isAuthenticated } = useAuthStore();
  const hasRestored = useRef(false);

  const restoreUserConversations = useCallback(async () => {
    if (hasRestored.current) {
      return;
    }

    try {
      setRestoring(true);
      hasRestored.current = true;

      // 수정: axios.get -> api.get
      const response = await api.get<LatestConversationResponse>(
        '/api/conversations/latest'
      );

      // 수정: 2중 중첩된 구조 처리
      const conversationData = response.data.data?.conversation || response.data.conversation;
      
      if (!response.data.success || !conversationData) {
        console.log('📭 복원할 인증 대화가 없습니다');
        return;
      }

      const messages: Message[] = conversationData.messages.map(
        (msg: ApiMessage) => ({
          id: msg.message_id,
          type: msg.message_type,
          content: msg.message,
          sql: msg.generated_sql || undefined,
          data: msg.result_data || undefined,  // 수정된 필드명 사용
        })
      );

      if (messages.length > 0) {
        // 백엔드에서 이미 시간순(오래된→최신)으로 정렬된 메시지 그대로 사용
        restoreMessages(messages);
      }

    } catch (error) {
      // 에러는 이미 interceptor에서 처리됨
      console.error('❌ 인증 사용자 대화 복원 중 오류:', error);
      hasRestored.current = false;
    } finally {
      setRestoring(false);
    }
  }, [restoreMessages, setRestoring]);

  const restoreConversations = useCallback(async () => {
    if (isAuthenticated) {
      await restoreUserConversations();
    } else {
      restoreMessages([]);
    }
  }, [isAuthenticated, restoreUserConversations, restoreMessages]);

  const resetRestoreFlag = useCallback(() => {
    hasRestored.current = false;
  }, []);

  return {
    restoreConversations,
    restoreUserConversations,
    resetRestoreFlag
  };
};
