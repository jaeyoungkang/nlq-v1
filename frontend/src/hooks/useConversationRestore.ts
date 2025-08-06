// hooks/useConversationRestore.ts
import { useCallback, useRef } from 'react';
import axios from 'axios';
import { useChatStore, Message } from '../stores/useChatStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useSession } from './useSession';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// API 응답 타입 정의
interface ApiMessage {
  message_id: string;
  message: string;
  message_type: 'user' | 'assistant';
  timestamp: string;
  query_type: string | null;
  generated_sql: string | null;
  execution_time_ms: number | null;
}

interface ConversationResponse {
  success: boolean;
  conversations: Array<{
    conversation_id: string;
    start_time: string;
    last_time: string;
    message_count: number;
    first_message: string;
  }>;
  count: number;
}

interface ConversationDetailsResponse {
  success: boolean;
  conversation_id: string;
  messages: ApiMessage[];
  message_count: number;
  error?: string;
}

export const useConversationRestore = () => {
  const { restoreMessages, setRestoring } = useChatStore();
  const { isAuthenticated } = useAuthStore();
  const { sessionId, isValidSessionId } = useSession();
  const hasRestored = useRef(false); // 복원 완료 플래그 (모든 타입 공통)

  // 인증된 사용자의 대화 복원
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

      // 사용자의 대화 목록 조회
      const conversationsResponse = await axios.get<ConversationResponse>(
        `${API_URL}/api/conversations?limit=1`
      );

      console.log('📋 인증 사용자 대화 목록 응답:', conversationsResponse.data);

      if (!conversationsResponse.data.success || conversationsResponse.data.count === 0) {
        console.log('📭 복원할 인증 대화가 없습니다');
        return;
      }

      // 가장 최근 대화 가져오기
      const latestConversation = conversationsResponse.data.conversations[0];
      console.log('📖 최근 인증 대화 조회:', latestConversation.conversation_id);

      // 대화 상세 내역 조회
      const detailsResponse = await axios.get<ConversationDetailsResponse>(
        `${API_URL}/api/conversations/${latestConversation.conversation_id}`
      );

      console.log('📝 인증 사용자 대화 상세 응답:', detailsResponse.data);

      if (!detailsResponse.data.success) {
        console.error('❌ 인증 대화 상세 조회 실패:', detailsResponse.data.error);
        return;
      }

      // 메시지 형식 변환
      const messages: Message[] = detailsResponse.data.messages.map((msg: ApiMessage) => ({
        id: msg.message_id,
        type: msg.message_type,
        content: msg.message,
        sql: msg.generated_sql || undefined,
        data: undefined
      }));

      if (messages.length > 0) {
        console.log(`✅ 인증 사용자 ${messages.length}개 메시지 복원 완료`);
        restoreMessages(messages);
      }

    } catch (error) {
      console.error('❌ 인증 사용자 대화 복원 중 오류:', error);
      hasRestored.current = false; // 오류 시 플래그 리셋
      if (axios.isAxiosError(error)) {
        console.error('네트워크 오류 상세:', {
          status: error.response?.status,
          data: error.response?.data,
          url: error.config?.url
        });
      }
    } finally {
      setRestoring(false);
    }
  }, [restoreMessages, setRestoring]);

  // 세션 기반 대화 복원 (비인증 사용자용)
  const restoreSessionConversations = useCallback(async () => {
    // 이미 복원했거나 sessionId가 유효하지 않으면 복원하지 않음
    if (hasRestored.current || !sessionId || sessionId === 'temp_session' || !isValidSessionId(sessionId)) {
      console.log('🔄 세션 기반 대화 복원 건너뜀:', { 
        hasRestored: hasRestored.current, 
        sessionId, 
        isValid: isValidSessionId(sessionId) 
      });
      return;
    }

    try {
      setRestoring(true);
      hasRestored.current = true; // 복원 시작 시 플래그 설정
      console.log('🔄 세션 기반 대화 복원 시작:', sessionId);

      // 세션의 대화 목록 조회
      const conversationsResponse = await axios.get<ConversationResponse>(
        `${API_URL}/api/conversations/session/${sessionId}?limit=1`
      );

      console.log('📋 세션 대화 목록 응답:', conversationsResponse.data);

      if (!conversationsResponse.data.success || conversationsResponse.data.count === 0) {
        console.log('📭 복원할 세션 대화가 없습니다');
        return;
      }

      // 가장 최근 대화 가져오기
      const latestConversation = conversationsResponse.data.conversations[0];
      console.log('📖 최근 세션 대화 조회:', latestConversation.conversation_id);

      // 대화 상세 내역 조회
      const detailsResponse = await axios.get<ConversationDetailsResponse>(
        `${API_URL}/api/conversations/session/${sessionId}/${latestConversation.conversation_id}`
      );

      console.log('📝 세션 대화 상세 응답:', detailsResponse.data);

      if (!detailsResponse.data.success) {
        console.error('❌ 세션 대화 상세 조회 실패:', detailsResponse.data.error);
        return;
      }

      // 메시지 형식 변환
      const messages: Message[] = detailsResponse.data.messages.map((msg: ApiMessage) => ({
        id: msg.message_id,
        type: msg.message_type,
        content: msg.message,
        sql: msg.generated_sql || undefined,
        data: undefined // 복원 시에는 데이터는 제외 (성능상 이유)
      }));

      if (messages.length > 0) {
        console.log(`✅ 세션 기반 ${messages.length}개 메시지 복원 완료`);
        restoreMessages(messages);
      }

    } catch (error) {
      console.error('❌ 세션 기반 대화 복원 중 오류:', error);
      hasRestored.current = false; // 오류 시 플래그 리셋
      // 네트워크 오류인 경우 자세한 로그
      if (axios.isAxiosError(error)) {
        console.error('네트워크 오류 상세:', {
          status: error.response?.status,
          data: error.response?.data,
          url: error.config?.url
        });
      }
    } finally {
      setRestoring(false);
    }
  }, [sessionId, isValidSessionId, restoreMessages, setRestoring]);

  // 전체 대화 복원 로직
  const restoreConversations = useCallback(async () => {
    // 인증된 사용자는 사용자 기반 복원
    if (isAuthenticated) {
      console.log('🔐 인증된 사용자 - 사용자 대화 복원');
      await restoreUserConversations();
      return;
    }

    // 비인증 사용자는 세션 기반 복원
    console.log('👤 비인증 사용자 - 세션 기반 복원');
    await restoreSessionConversations();
  }, [isAuthenticated, restoreUserConversations, restoreSessionConversations]);

  // 복원 상태 리셋 함수 (로그인/로그아웃 시 사용)
  const resetRestoreFlag = useCallback(() => {
    hasRestored.current = false;
    console.log('🔄 복원 플래그 리셋');
  }, []);

  return {
    restoreConversations,
    restoreSessionConversations,
    restoreUserConversations,
    resetRestoreFlag
  };
};