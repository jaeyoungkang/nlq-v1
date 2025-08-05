/**
 * 메인 앱 컨트롤러 (ES6 모듈)
 * 책임: 전체 앱 로직 조율, 모듈 간 통신 관리
 */

import { ConversationStorage } from './conversation-storage.js';
import { APIClient, APIError, APIResponse } from './api-client.js';
import { UIManager } from './ui-manager.js';

export class AppController {
    constructor() {
        this.storage = new ConversationStorage();
        this.apiClient = new APIClient();
        this.uiManager = new UIManager();
        this.conversationHistory = [];
        this.isProcessing = false;
        
        // 앱 상태
        this.state = {
            initialized: false,
            sessionActive: false,
            lastRequestTime: null,
            totalRequests: 0,
            errors: []
        };
    }

    /**
     * 앱 초기화
     */
    async init() {
        try {
            console.log('🚀 BigQuery Assistant 초기화 시작');
            
            // UI 초기화
            this.uiManager.init();
            
            // 이벤트 바인딩
            this.bindEvents();
            
            // 세션 복원
            await this.restoreSession();
            
            // 서비스 상태 확인
            await this.checkServiceHealth();
            
            this.state.initialized = true;
            console.log('✅ BigQuery Assistant 초기화 완료');
            
        } catch (error) {
            console.error('❌ 앱 초기화 실패:', error);
            this.handleInitializationError(error);
        }
    }

    /**
     * 이벤트 바인딩
     */
    bindEvents() {
        // 메시지 전송 이벤트
        document.addEventListener('message-submit', (e) => {
            this.handleMessageSubmit(e.detail.message);
        });

        // 메시지 추가 이벤트
        document.addEventListener('message-added', (e) => {
            this.handleMessageAdded(e.detail);
        });

        // 페이지 언로드 시 정리
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // 온라인/오프라인 상태 감지
        window.addEventListener('online', () => {
            console.log('🌐 온라인 상태로 변경');
            this.checkServiceHealth();
        });

        window.addEventListener('offline', () => {
            console.log('📴 오프라인 상태로 변경');
            this.showOfflineMessage();
        });

        // 에러 처리
        window.addEventListener('error', (e) => {
            this.handleGlobalError(e.error);
        });

        window.addEventListener('unhandledrejection', (e) => {
            this.handleGlobalError(e.reason);
        });
    }

    /**
     * 메시지 전송 처리
     * @param {string} message - 사용자 메시지
     */
    async handleMessageSubmit(message) {
        if (this.isProcessing) {
            console.log('⏳ 이미 처리 중인 요청이 있습니다');
            return;
        }

        if (!message || message.trim().length === 0) {
            this.showError('메시지를 입력해주세요.');
            return;
        }

        this.isProcessing = true;
        this.state.lastRequestTime = new Date().toISOString();
        this.state.totalRequests++;

        try {
            // 사용자 메시지 추가
            this.addUserMessage(message);
            
            // 입력창 정리
            this.uiManager.clearInput();
            
            // 웰컴 메시지 숨기기
            this.uiManager.hideWelcomeMessage();
            
            // 로딩 메시지 표시
            const loadingId = this.uiManager.addLoadingMessage();
            
            // API 요청
            const context = this.buildContext();
            const response = await this.apiClient.sendChatMessage(message, context);
            
            // 로딩 메시지 제거
            this.uiManager.removeMessage(loadingId);
            
            // 응답 처리
            if (APIResponse.isSuccess(response)) {
                await this.handleChatResponse(response);
                this.updateConversationHistory(message, response);
            } else {
                this.showError(APIResponse.getErrorMessage(response));
            }
            
        } catch (error) {
            console.error('❌ 메시지 처리 실패:', error);
            this.handleMessageError(error);
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * 사용자 메시지 추가
     * @param {string} message - 메시지 내용
     */
    addUserMessage(message) {
        this.uiManager.addMessage('user', 'User', this.uiManager.escapeHtml(message));
        
        // 스토리지에 저장
        this.storage.saveMessage({
            type: 'user',
            content: message,
            metadata: {
                timestamp: new Date().toISOString(),
                requestId: this.generateRequestId()
            }
        });
    }

    /**
     * 챗봇 응답 처리
     * @param {Object} data - API 응답 데이터
     */
    async handleChatResponse(data) {
        const result = data.result;
        const category = data.category;
        let content = '';
        
        try {
            // 응답 타입별 처리
            switch (result.type) {
                case 'query_result':
                    content = this.formatQueryResult(result, data);
                    break;
                    
                case 'analysis':
                    content = this.uiManager.formatMarkdown(result.analysis);
                    break;
                    
                case 'metadata':
                    content = this.uiManager.formatMarkdown(result.response);
                    break;
                    
                case 'guide':
                    content = this.uiManager.formatMarkdown(result.guide);
                    break;
                    
                case 'out_of_scope':
                    content = this.uiManager.formatMarkdown(result.response);
                    break;
                    
                case 'error':
                    content = `<div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">${this.uiManager.escapeHtml(result.error)}</div>`;
                    break;
                    
                default:
                    content = '<div class="text-gray-500">알 수 없는 응답 형식입니다.</div>';
            }

            // AI 응답 추가
            this.uiManager.addMessage('assistant', 'Assistant', content);
            
            // 스토리지에 저장
            this.storage.saveMessage({
                type: 'assistant',
                content: content,
                metadata: {
                    category: category,
                    executionTime: APIResponse.getExecutionTime(data),
                    hasResults: result.data ? result.data.length > 0 : false,
                    requestId: data.request_id || this.generateRequestId()
                }
            });
            
        } catch (error) {
            console.error('❌ 응답 처리 중 오류:', error);
            this.showError('응답을 처리하는 중 오류가 발생했습니다.');
        }
    }

    /**
     * 쿼리 결과 포맷팅
     * @param {Object} result - 쿼리 결과
     * @param {Object} data - 전체 응답 데이터
     * @returns {string} 포맷된 HTML
     */
    formatQueryResult(result, data) {
        let content = '';
        
        // SQL 표시
        if (result.generated_sql) {
            content += `
                <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
                    <div class="text-xs text-gray-500 mb-2 uppercase tracking-wide font-semibold">생성된 SQL</div>
                    <pre class="text-sm font-mono text-gray-800 whitespace-pre-wrap overflow-x-auto">${this.uiManager.escapeHtml(result.generated_sql)}</pre>
                </div>
            `;
        }
        
        // 결과 테이블 표시
        if (result.data && result.data.length > 0) {
            content += this.uiManager.createResultsTable(
                result.data, 
                result.row_count, 
                APIResponse.getExecutionTime(data)
            );
        } else if (result.data && result.data.length === 0) {
            content += '<div class="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg">조회 결과가 없습니다.</div>';
        }
        
        return content;
    }

    /**
     * 컨텍스트 구성
     * @returns {Object} 대화 컨텍스트
     */
    buildContext() {
        const recentHistory = this.conversationHistory.slice(-2);
        const context = {
            sessionId: this.storage.currentSessionId,
            timestamp: new Date().toISOString(),
            requestCount: this.state.totalRequests
        };
        
        // 최근 쿼리 결과가 있으면 포함
        for (let i = recentHistory.length - 1; i >= 0; i--) {
            const item = recentHistory[i];
            if (item.type === 'query_result' && item.data) {
                context.previous_data = item.data.slice(0, 20); // 최대 20행
                context.previous_sql = item.generated_sql;
                break;
            }
        }
        
        context.previous_queries = recentHistory.filter(h => h.type === 'query_result').length;
        
        return context;
    }

    /**
     * 대화 기록 업데이트
     * @param {string} userMessage - 사용자 메시지
     * @param {Object} responseData - API 응답 데이터
     */
    updateConversationHistory(userMessage, responseData) {
        // 사용자 메시지 기록
        this.conversationHistory.push({
            type: 'user_message',
            message: userMessage,
            timestamp: new Date().toISOString()
        });
        
        // AI 응답 기록
        const historyItem = {
            type: responseData.result.type,
            category: responseData.category,
            timestamp: new Date().toISOString(),
            requestId: responseData.request_id
        };
        
        // 타입별 추가 정보
        if (responseData.result.type === 'query_result') {
            historyItem.data = responseData.result.data;
            historyItem.generated_sql = responseData.result.generated_sql;
            historyItem.row_count = responseData.result.row_count;
        } else if (responseData.result.type === 'metadata') {
            historyItem.metadata = responseData.result.raw_metadata;
        }
        
        this.conversationHistory.push(historyItem);
        
        // 히스토리 크기 제한 (최대 20개 항목)
        if (this.conversationHistory.length > 20) {
            this.conversationHistory = this.conversationHistory.slice(-20);
        }
    }

    /**
     * 세션 복원
     */
    async restoreSession() {
        try {
            const session = this.storage.getCurrentSession();
            if (session && session.messages.length > 0) {
                console.log(`📂 세션 복원: ${session.messages.length}개 메시지`);
                
                this.uiManager.hideWelcomeMessage();
                this.uiManager.showRestoreNotification(session.messages.length);
                
                // 메시지 복원
                session.messages.forEach(msg => {
                    const messageDiv = this.uiManager.createMessageElement(
                        msg.type === 'user' ? 'user' : 'assistant',
                        msg.type === 'user' ? 'User' : 'Assistant',
                        msg.content
                    );
                    this.uiManager.elements.conversationArea?.appendChild(messageDiv);
                });
                
                this.uiManager.scrollToBottom();
                this.state.sessionActive = true;
            }
        } catch (error) {
            console.error('❌ 세션 복원 실패:', error);
        }
    }

    /**
     * 서비스 상태 확인
     */
    async checkServiceHealth() {
        try {
            const health = await this.apiClient.checkHealth();
            console.log('💚 서비스 상태:', health.status);
            
            if (health.status === 'degraded') {
                this.showWarning('일부 서비스에 문제가 있습니다. 기능이 제한될 수 있습니다.');
            }
            
        } catch (error) {
            console.error('❌ 서비스 상태 확인 실패:', error);
            this.showWarning('서비스 연결을 확인할 수 없습니다.');
        }
    }

    /**
     * 메시지 추가 이벤트 처리
     * @param {Object} detail - 이벤트 상세 정보
     */
    handleMessageAdded(detail) {
        console.log(`📝 메시지 추가: ${detail.type} - ${detail.label}`);
        
        // 접근성: 스크린 리더 사용자를 위한 알림
        if (detail.type === 'assistant') {
            setTimeout(() => {
                const announcement = document.createElement('div');
                announcement.setAttribute('aria-live', 'polite');
                announcement.setAttribute('aria-atomic', 'true');
                announcement.className = 'sr-only';
                announcement.textContent = 'AI 응답이 도착했습니다.';
                document.body.appendChild(announcement);
                
                setTimeout(() => announcement.remove(), 1000);
            }, 500);
        }
    }

    /**
     * 메시지 처리 오류 핸들링
     * @param {Error} error - 오류 객체
     */
    handleMessageError(error) {
        this.state.errors.push({
            timestamp: new Date().toISOString(),
            error: error.message,
            type: error.constructor.name
        });

        if (error instanceof APIError) {
            this.showError(error.getUserMessage());
            error.log();
        } else {
            this.showError('메시지 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
            console.error('❌ 예상치 못한 오류:', error);
        }
    }

    /**
     * 초기화 오류 처리
     * @param {Error} error - 초기화 오류
     */
    handleInitializationError(error) {
        const errorMessage = '앱을 초기화하는 중 문제가 발생했습니다. 페이지를 새로고침해주세요.';
        
        // 오류 메시지 표시
        document.body.innerHTML = `
            <div class="min-h-screen flex items-center justify-center bg-gray-50">
                <div class="max-w-md mx-auto text-center p-6">
                    <div class="text-6xl mb-4">😞</div>
                    <h1 class="text-xl font-semibold text-gray-900 mb-2">앱 초기화 실패</h1>
                    <p class="text-gray-600 mb-6">${errorMessage}</p>
                    <button onclick="window.location.reload()" 
                            class="bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 transition">
                        새로고침
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 전역 오류 처리
     * @param {Error} error - 전역 오류
     */
    handleGlobalError(error) {
        console.error('🚨 전역 오류:', error);
        
        this.state.errors.push({
            timestamp: new Date().toISOString(),
            error: error.message || String(error),
            type: 'global_error',
            stack: error.stack
        });

        // 치명적 오류가 아닌 경우에만 사용자에게 알림
        if (!this.isCriticalError(error)) {
            this.showError('예상치 못한 오류가 발생했습니다.');
        }
    }

    /**
     * 치명적 오류 여부 확인
     * @param {Error} error - 확인할 오류
     * @returns {boolean} 치명적 오류 여부
     */
    isCriticalError(error) {
        const criticalErrors = [
            'ChunkLoadError',
            'Script error',
            'ResizeObserver loop limit exceeded'
        ];
        
        return criticalErrors.some(criticalError => 
            error.message?.includes(criticalError) || 
            error.name === criticalError
        );
    }

    /**
     * 오프라인 메시지 표시
     */
    showOfflineMessage() {
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-yellow-500 text-white p-4 rounded-lg shadow-lg z-50';
        notification.innerHTML = `
            <div class="flex items-center space-x-2">
                <span>📴</span>
                <span>인터넷 연결이 끊어졌습니다</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * 오류 메시지 표시
     * @param {string} message - 오류 메시지
     */
    showError(message) {
        const content = `<div class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">${this.uiManager.escapeHtml(message)}</div>`;
        this.uiManager.addMessage('assistant', 'Assistant', content);
        
        // 스토리지에도 저장
        this.storage.saveMessage({
            type: 'assistant',
            content: content,
            metadata: { 
                isError: true,
                timestamp: new Date().toISOString()
            }
        });
    }

    /**
     * 경고 메시지 표시
     * @param {string} message - 경고 메시지
     */
    showWarning(message) {
        const content = `<div class="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg">${this.uiManager.escapeHtml(message)}</div>`;
        this.uiManager.addMessage('assistant', 'Assistant', content);
    }

    /**
     * 요청 ID 생성
     * @returns {string} 고유 요청 ID
     */
    generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 앱 상태 정보 반환
     * @returns {Object} 앱 상태
     */
    getAppState() {
        return {
            ...this.state,
            storage: this.storage.getStorageInfo(),
            ui: this.uiManager.getState(),
            conversationHistory: this.conversationHistory.length
        };
    }

    /**
     * 디버그 정보 출력
     */
    debug() {
        console.group('🔍 BigQuery Assistant 디버그 정보');
        console.log('앱 상태:', this.getAppState());
        console.log('대화 기록:', this.conversationHistory);
        console.log('스토리지 정보:', this.storage.getStorageInfo());
        console.log('UI 상태:', this.uiManager.getState());
        console.groupEnd();
    }

    /**
     * 세션 초기화
     */
    resetSession() {
        if (confirm('현재 대화를 삭제하고 새로 시작하시겠습니까?')) {
            this.storage.clearCurrentSession();
            this.conversationHistory = [];
            location.reload();
        }
    }

    /**
     * 앱 정리 (메모리 누수 방지)
     */
    cleanup() {
        console.log('🧹 앱 정리 시작');
        
        try {
            // UI 관리자 정리
            this.uiManager.cleanup();
            
            // 상태 초기화
            this.isProcessing = false;
            this.conversationHistory = [];
            
            console.log('✅ 앱 정리 완료');
        } catch (error) {
            console.error('❌ 앱 정리 중 오류:', error);
        }
    }

    /**
     * 성능 메트릭 수집
     * @returns {Object} 성능 정보
     */
    getPerformanceMetrics() {
        const navigation = performance.getEntriesByType('navigation')[0];
        const paint = performance.getEntriesByType('paint');
        
        return {
            pageLoad: {
                domContentLoaded: navigation?.domContentLoadedEventEnd - navigation?.domContentLoadedEventStart,
                loadComplete: navigation?.loadEventEnd - navigation?.loadEventStart,
                totalTime: navigation?.loadEventEnd - navigation?.fetchStart
            },
            paint: {
                firstPaint: paint.find(p => p.name === 'first-paint')?.startTime,
                firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime
            },
            memory: {
                used: performance.memory?.usedJSHeapSize,
                total: performance.memory?.totalJSHeapSize,
                limit: performance.memory?.jsHeapSizeLimit
            },
            requests: {
                total: this.state.totalRequests,
                errors: this.state.errors.length,
                errorRate: this.state.totalRequests > 0 ? (this.state.errors.length / this.state.totalRequests * 100).toFixed(2) + '%' : '0%'
            }
        };
    }

    /**
     * 접근성 개선 기능들
     */
    enhanceAccessibility() {
        // 키보드 단축키 등록
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter: 메시지 전송
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const message = this.uiManager.getInputValue();
                if (message) {
                    this.handleMessageSubmit(message);
                }
            }
            
            // Ctrl/Cmd + K: 입력창 포커스
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.uiManager.focusInput();
            }
            
            // Ctrl/Cmd + Shift + R: 세션 리셋
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'R') {
                e.preventDefault();
                this.resetSession();
            }
        });

        // 고대비 모드 지원
        if (window.matchMedia('(prefers-contrast: high)').matches) {
            document.documentElement.classList.add('high-contrast');
        }

        // 모션 감소 모드 지원
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.documentElement.classList.add('reduced-motion');
        }
    }
}

// 전역 앱 인스턴스 생성 및 내보내기
export const app = new AppController();

// 개발 모드에서 디버그 기능 노출
if (process.env.NODE_ENV === 'development' || window.location.hostname === 'localhost') {
    window.bqApp = app;
    window.bqDebug = () => app.debug();
    window.bqReset = () => app.resetSession();
    window.bqPerf = () => console.table(app.getPerformanceMetrics());
}