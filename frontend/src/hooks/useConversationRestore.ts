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
  query_result_data?: Record<string, unknown>[];
  query_row_count?: number;
}

interface LatestConversationResponse {
  success: boolean;
  conversation: {
    conversation_id: string;
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

      if (!response.data.success || !response.data.conversation) {
        console.log('📭 복원할 인증 대화가 없습니다');
        return;
      }

      const messages: Message[] = response.data.conversation.messages.map(
        (msg: ApiMessage) => ({
          id: msg.message_id,
          type: msg.message_type,
          content: msg.message,
          sql: msg.generated_sql || undefined,
          data: msg.query_result_data || undefined,
        })
      );

      if (messages.length > 0) {
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
