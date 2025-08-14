// API 관련 타입 정의 중앙화

// SSE 이벤트 타입 정의
export interface SSEProgressEvent {
  stage: string;
  message: string;
  generated_sql?: string;
}

export interface SSEResultEvent {
  success: boolean;
  request_id: string;
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
  conversation_saved?: boolean;
  user?: {
    user_id: string;
    email: string;
  };
}

export interface SSEErrorEvent {
  error: string;
  error_type: string;
}

// 인증 관련 타입
export interface AuthUser {
  user_id: string;
  email: string;
  name?: string;
}

export interface LoginResponse {
  success: boolean;
  access_token: string;
  user: AuthUser;
}

export interface AuthVerifyResponse {
  authenticated: boolean;
  user?: AuthUser;
}

// 채팅 관련 타입
export interface ChatMessage {
  type: 'user' | 'assistant';
  content: string;
  sql?: string;
  data?: Record<string, unknown>[];
  isProgress?: boolean;
}

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  success: boolean;
  result: {
    type: 'query_result' | 'guide_result' | 'analysis_result' | 'metadata_result' | 'out_of_scope_result';
    content?: string;
    generated_sql?: string;
    data?: Record<string, unknown>[];
    row_count?: number;
  };
  error?: string;
}