// hooks/useConversationRestore.ts - 로그인 필수 버전
import { useCallback, useRef } from 'react';
import axios from 'axios';
import { useChatStore, Message } from '../stores/useChatStore';
import { useAuthStore } from '../stores/useAuthStore';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// 인증된 사용자 대화 API 응답 타입
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

// API 에러 응답 타입
interface ApiErrorResponse {
  success: boolean;
  error: string;
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
  const hasRestored = useRef(false); // 복원 완료 플래그

  // 인증된 사용자의 대화 복원만 지원
  const restoreUserConversations = useCallback(async () => {
    // 이미 복원했으면 건너뛰기
    if (hasRestored.current) {
      console.log('🔄 인증 사용자 대화 복원 건너뜀: 이미 복원 완료');
      return;
    }

    try {
      setRestoring(true);
      hasRestored.current = true; // 복원 시작 시 플래그 설정
      console.log('🔐 인증된 사용자 대화 복원 시작');

      // 가장 최근 대화의 모든 정보를 한 번에 가져오는 최적화된 API 호출
      const response = await axios.get<LatestConversationResponse>(
        `${API_URL}/api/conversations/latest`
      );

      console.log('📝 인증 사용자 최근 대화 상세 응답:', response.data);

      if (!response.data.success) {
        console.error('❌ 인증 대화 상세 조회 실패:', response.data.error);
        return;
      }
      
      if (!response.data.conversation) {
        console.log('📭 복원할 인증 대화가 없습니다');
        return;
      }

      const messages: Message[] = response.data.conversation.messages.map(
        (msg: ApiMessage) => ({
          id: msg.message_id,
          type: msg.message_type,
          content: msg.message, // assistant 메시지 내용도 그대로 복원
          sql: msg.generated_sql || undefined,
          data: msg.query_result_data || undefined, // 저장된 쿼리 결과 복원
        })
      );

      if (messages.length > 0) {
        console.log(`✅ 인증 사용자 ${messages.length}개 메시지 복원 완료`);
        restoreMessages(messages);
      }

    } catch (error) {
      console.error('❌ 인증 사용자 대화 복원 중 오류:', error);
      hasRestored.current = false; // 오류 시 플래그 리셋
      if (axios.isAxiosError<ApiErrorResponse>(error)) {
        console.error('네트워크 오류 상세:', {
          status: error.response?.status,
          data: error.response?.data,
          url: error.config?.url
        });
        
        // 401 오류인 경우 로그인 필요 안내
        if (error.response?.status === 401) {
          console.log('🔐 인증이 필요한 요청 - 로그인 후 이용 가능');
        }
      }
    } finally {
      setRestoring(false);
    }
  }, [restoreMessages, setRestoring]);

  // 전체 대화 복원 로직 (인증된 사용자만)
  const restoreConversations = useCallback(async () => {
    // 인증된 사용자만 대화 복원
    if (isAuthenticated) {
      console.log('🔐 인증된 사용자 - 대화 복원 시작');
      await restoreUserConversations();
    } else {
      console.log('👤 비인증 사용자 - 대화 복원 건너뜀 (로그인 필요)');
      
      // 비인증 사용자는 빈 대화로 시작
      restoreMessages([]);
    }
  }, [isAuthenticated, restoreUserConversations, restoreMessages]);

  // 복원 상태 리셋 함수 (로그인/로그아웃 시 사용)
  const resetRestoreFlag = useCallback(() => {
    hasRestored.current = false;
    console.log('🔄 복원 플래그 리셋');
  }, []);

  return {
    restoreConversations,
    restoreUserConversations,
    resetRestoreFlag
  };
};