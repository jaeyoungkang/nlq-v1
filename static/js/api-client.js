/**
 * API 클라이언트 모듈 (ES6 모듈)
 * 책임: 백엔드 API와의 통신 관리
 */

export class APIClient {
    constructor() {
        this.baseURL = '';
        this.timeout = 30000; // 30초 타임아웃
        this.retryAttempts = 3;
        this.retryDelay = 1000; // 1초
    }

    /**
     * HTTP 요청 기본 메서드
     * @param {string} endpoint - API 엔드포인트
     * @param {Object} options - 요청 옵션
     * @returns {Promise<Object>} API 응답
     * @private
     */
    async _request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
        
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Request-ID': requestId,
                ...options.headers
            },
            ...options
        };

        console.log(`🌐 [${requestId}] ${config.method} ${endpoint}`);
        
        // 타임아웃 설정
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        config.signal = controller.signal;

        try {
            const response = await fetch(url, config);
            clearTimeout(timeoutId);
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new APIError(
                    data.error || `HTTP ${response.status}`,
                    response.status,
                    data.error_type || 'http_error',
                    data
                );
            }

            console.log(`✅ [${requestId}] 응답 성공 (${response.status})`);
            return data;
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new APIError('요청 시간 초과', 408, 'timeout_error');
            }
            
            if (error instanceof APIError) {
                throw error;
            }
            
            // 네트워크 오류
            console.error(`❌ [${requestId}] 네트워크 오류:`, error);
            throw new APIError(
                `네트워크 오류: ${error.message}`,
                0,
                'network_error'
            );
        }
    }

    /**
     * 재시도 로직이 포함된 요청
     * @param {string} endpoint - API 엔드포인트
     * @param {Object} options - 요청 옵션
     * @returns {Promise<Object>} API 응답
     * @private
     */
    async _requestWithRetry(endpoint, options = {}) {
        let lastError;
        
        for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
            try {
                return await this._request(endpoint, options);
            } catch (error) {
                lastError = error;
                
                // 재시도하지 않을 오류들
                if (error.status === 400 || error.status === 401 || error.status === 403) {
                    throw error;
                }
                
                if (attempt < this.retryAttempts) {
                    const delay = this.retryDelay * Math.pow(2, attempt - 1); // 지수 백오프
                    console.log(`🔄 재시도 ${attempt}/${this.retryAttempts} (${delay}ms 후)`);
                    await this._sleep(delay);
                } else {
                    console.error(`❌ 모든 재시도 실패 (${this.retryAttempts}회)`);
                }
            }
        }
        
        throw lastError;
    }

    /**
     * 채팅 메시지 전송
     * @param {string} message - 사용자 메시지
     * @param {Object} context - 대화 컨텍스트
     * @returns {Promise<Object>} 챗봇 응답
     */
    async sendChatMessage(message, context = {}) {
        if (!message || typeof message !== 'string') {
            throw new APIError('메시지가 필요합니다', 400, 'validation_error');
        }

        if (message.length > 1000) {
            throw new APIError('메시지가 너무 깁니다 (최대 1000자)', 400, 'validation_error');
        }

        const payload = {
            message: message.trim(),
            context: {
                timestamp: new Date().toISOString(),
                userAgent: navigator.userAgent,
                language: navigator.language,
                ...context
            }
        };

        return await this._requestWithRetry('/api/chat', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * SQL 쿼리 검증
     * @param {string} sql - SQL 쿼리
     * @returns {Promise<Object>} 검증 결과
     */
    async validateSQL(sql) {
        if (!sql || typeof sql !== 'string') {
            throw new APIError('SQL 쿼리가 필요합니다', 400, 'validation_error');
        }

        if (sql.length > 10000) {
            throw new APIError('SQL 쿼리가 너무 깁니다 (최대 10,000자)', 400, 'validation_error');
        }

        return await this._request('/api/validate-sql', {
            method: 'POST',
            body: JSON.stringify({ sql: sql.trim() })
        });
    }

    /**
     * 헬스 체크
     * @returns {Promise<Object>} 서비스 상태
     */
    async checkHealth() {
        return await this._request('/api/health');
    }

    /**
     * 지연 유틸리티
     * @param {number} ms - 지연 시간 (밀리초)
     * @private
     */
    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * API 오류 클래스
 */
export class APIError extends Error {
    constructor(message, status = 0, type = 'unknown', details = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.type = type;
        this.details = details;
        this.timestamp = new Date().toISOString();
    }

    /**
     * 사용자 친화적 오류 메시지 반환
     * @returns {string} 사용자용 메시지
     */
    getUserMessage() {
        switch (this.type) {
            case 'validation_error':
                return this.message;
            
            case 'timeout_error':
                return '요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.';
            
            case 'network_error':
                return '네트워크 연결을 확인하고 다시 시도해주세요.';
            
            case 'service_error':
                return '서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.';
            
            case 'rate_limit_exceeded':
                return '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.';
            
            default:
                if (this.status >= 500) {
                    return '서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.';
                } else if (this.status >= 400) {
                    return this.message || '요청에 문제가 있습니다.';
                } else {
                    return '알 수 없는 오류가 발생했습니다.';
                }
        }
    }

    /**
     * 오류를 로그에 기록
     */
    log() {
        console.group(`❌ APIError: ${this.type}`);
        console.error('Message:', this.message);
        console.error('Status:', this.status);
        console.error('Type:', this.type);
        console.error('Timestamp:', this.timestamp);
        if (this.details) {
            console.error('Details:', this.details);
        }
        console.groupEnd();
    }
}

/**
 * API 응답 유틸리티 클래스
 */
export class APIResponse {
    /**
     * 성공 응답인지 확인
     * @param {Object} response - API 응답
     * @returns {boolean} 성공 여부
     */
    static isSuccess(response) {
        return response && response.success === true;
    }

    /**
     * 오류 응답에서 사용자 메시지 추출
     * @param {Object} response - API 응답
     * @returns {string} 사용자용 오류 메시지
     */
    static getErrorMessage(response) {
        if (!response) return '알 수 없는 오류가 발생했습니다.';
        
        if (response.error) {
            // 표준 오류 응답 형식
            const error = new APIError(
                response.error,
                response.status || 0,
                response.error_type || 'unknown',
                response.details
            );
            return error.getUserMessage();
        }
        
        return '요청 처리 중 오류가 발생했습니다.';
    }

    /**
     * 응답에서 실행 시간 추출
     * @param {Object} response - API 응답
     * @returns {number|null} 실행 시간 (밀리초)
     */
    static getExecutionTime(response) {
        return response?.performance?.execution_time_ms || 
               response?.execution_time_ms || 
               null;
    }

    /**
     * 응답 데이터 검증
     * @param {Object} response - API 응답
     * @param {Array<string>} requiredFields - 필수 필드들
     * @returns {boolean} 유효성 여부
     */
    static validate(response, requiredFields = []) {
        if (!response || typeof response !== 'object') {
            return false;
        }

        return requiredFields.every(field => {
            const keys = field.split('.');
            let current = response;
            
            for (const key of keys) {
                if (current === null || current === undefined || !(key in current)) {
                    return false;
                }
                current = current[key];
            }
            
            return true;
        });
    }
}

// 기본 API 클라이언트 인스턴스 생성 및 내보내기
export const apiClient = new APIClient();