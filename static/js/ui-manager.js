/**
 * UI 관리자 모듈 (ES6 모듈)
 * 책임: DOM 조작, 이벤트 처리, UI 상태 관리
 */

export class UIManager {
    constructor() {
        this.elements = {};
        this.messageIdCounter = 0;
        this.isComposing = false;
        this.eventListeners = new Map(); // 이벤트 리스너 추적
    }

    /**
     * UI 초기화
     */
    init() {
        this.initializeElements();
        this.bindEvents();
        this.setupAccessibility();
        console.log('🎨 UI 관리자 초기화 완료');
    }

    /**
     * DOM 요소들 초기화
     */
    initializeElements() {
        const elementIds = [
            'queryForm', 'messageInput', 'sendButton', 
            'conversationArea', 'sampleButtons'
        ];

        elementIds.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                this.elements[id] = element;
            } else {
                console.warn(`⚠️ 요소를 찾을 수 없습니다: ${id}`);
            }
        });
    }

    /**
     * 이벤트 바인딩
     */
    bindEvents() {
        // 폼 제출 이벤트
        if (this.elements.queryForm) {
            this.addEventListener(this.elements.queryForm, 'submit', (e) => {
                e.preventDefault();
                this.dispatchCustomEvent('message-submit', {
                    message: this.getInputValue()
                });
            });
        }

        // 입력창 이벤트들
        if (this.elements.messageInput) {
            // 키보드 이벤트
            this.addEventListener(this.elements.messageInput, 'keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey && !this.isComposing) {
                    e.preventDefault();
                    this.elements.queryForm.dispatchEvent(new Event('submit'));
                }
            });

            // 입력 이벤트
            this.addEventListener(this.elements.messageInput, 'input', () => {
                this.adjustTextareaHeight();
                this.updateSendButtonState();
            });

            // IME 이벤트 (한글 입력 등)
            this.addEventListener(this.elements.messageInput, 'compositionstart', () => {
                this.isComposing = true;
            });

            this.addEventListener(this.elements.messageInput, 'compositionend', () => {
                this.isComposing = false;
            });
        }

        // 샘플 질문 버튼 이벤트
        if (this.elements.sampleButtons) {
            this.addEventListener(this.elements.sampleButtons, 'click', (e) => {
                if (e.target.tagName === 'BUTTON') {
                    this.setInputValue(e.target.textContent);
                    this.focusInput();
                    this.adjustTextareaHeight();
                }
            });
        }

        // 윈도우 리사이즈 이벤트
        this.addEventListener(window, 'resize', this.debounce(() => {
            this.adjustTextareaHeight();
        }, 250));
    }

    /**
     * 접근성 설정
     */
    setupAccessibility() {
        // ARIA 속성 설정
        if (this.elements.conversationArea) {
            this.elements.conversationArea.setAttribute('role', 'log');
            this.elements.conversationArea.setAttribute('aria-live', 'polite');
            this.elements.conversationArea.setAttribute('aria-label', '대화 기록');
        }

        // 키보드 네비게이션 지원
        document.addEventListener('keydown', (e) => {
            // Alt + I: 입력창 포커스
            if (e.altKey && e.key === 'i') {
                e.preventDefault();
                this.focusInput();
            }
            
            // Alt + C: 대화창 포커스
            if (e.altKey && e.key === 'c') {
                e.preventDefault();
                this.elements.conversationArea?.focus();
            }
        });
    }

    /**
     * 입력값 가져오기
     * @returns {string} 입력된 메시지
     */
    getInputValue() {
        return this.elements.messageInput?.value.trim() || '';
    }

    /**
     * 입력값 설정
     * @param {string} value - 설정할 값
     */
    setInputValue(value) {
        if (this.elements.messageInput) {
            this.elements.messageInput.value = value;
            this.updateSendButtonState();
        }
    }

    /**
     * 입력창 초기화
     */
    clearInput() {
        this.setInputValue('');
        this.adjustTextareaHeight();
    }

    /**
     * 입력창에 포커스
     */
    focusInput() {
        if (this.elements.messageInput) {
            this.elements.messageInput.focus();
        }
    }

    /**
     * 텍스트 영역 높이 자동 조정
     */
    adjustTextareaHeight() {
        const textarea = this.elements.messageInput;
        if (!textarea) return;

        textarea.style.height = 'auto';
        const newHeight = Math.min(textarea.scrollHeight, 120);
        textarea.style.height = newHeight + 'px';
    }

    /**
     * 전송 버튼 상태 업데이트
     */
    updateSendButtonState() {
        const hasContent = this.getInputValue().length > 0;
        const button = this.elements.sendButton;
        
        if (button) {
            button.disabled = !hasContent;
            button.classList.toggle('opacity-50', !hasContent);
            button.classList.toggle('cursor-not-allowed', !hasContent);
        }
    }

    /**
     * 메시지 요소 생성
     * @param {string} type - 메시지 타입 ('user' | 'assistant')
     * @param {string} label - 표시할 라벨
     * @param {string} content - 메시지 내용
     * @param {string} id - 요소 ID (선택사항)
     * @returns {HTMLElement} 생성된 메시지 요소
     */
    createMessageElement(type, label, content, id = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message mb-8`;
        if (id) messageDiv.id = id;
        
        const labelClass = type === 'user' ? 'text-primary-500' : 'text-gray-700';
        const contentClass = type === 'user' 
            ? 'bg-primary-50 border-l-4 border-primary-500 p-4 rounded-lg' 
            : '';
        
        messageDiv.innerHTML = `
            <div class="text-sm font-semibold ${labelClass} mb-2">${this.escapeHtml(label)}</div>
            <div class="text-sm leading-relaxed ${contentClass}">${content}</div>
        `;
        
        // 접근성 속성 추가
        messageDiv.setAttribute('role', 'article');
        messageDiv.setAttribute('aria-label', `${label} 메시지`);
        
        return messageDiv;
    }

    /**
     * 메시지 추가
     * @param {string} type - 메시지 타입
     * @param {string} label - 라벨
     * @param {string} content - 내용
     * @param {string} id - ID (선택사항)
     */
    addMessage(type, label, content, id = null) {
        const messageElement = this.createMessageElement(type, label, content, id);
        this.elements.conversationArea?.appendChild(messageElement);
        this.scrollToBottom();
        
        // 새 메시지 추가 이벤트 발생
        this.dispatchCustomEvent('message-added', {
            type, label, content, element: messageElement
        });
    }

    /**
     * 로딩 메시지 추가
     * @returns {string} 로딩 메시지 ID
     */
    addLoadingMessage() {
        const loadingId = `loading-${++this.messageIdCounter}`;
        const content = `
            <div class="flex items-center space-x-2 text-gray-600">
                <span>처리 중</span>
                <div class="flex space-x-1">
                    <div class="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
                    <div class="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
                    <div class="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
                </div>
            </div>
        `;
        
        this.addMessage('assistant', 'Assistant', content, loadingId);
        return loadingId;
    }

    /**
     * 메시지 제거
     * @param {string} messageId - 제거할 메시지 ID
     */
    removeMessage(messageId) {
        const messageElement = document.getElementById(messageId);
        if (messageElement) {
            // 부드러운 제거 애니메이션
            messageElement.style.transition = 'opacity 0.3s ease';
            messageElement.style.opacity = '0';
            
            setTimeout(() => {
                messageElement.remove();
            }, 300);
        }
    }

    /**
     * 결과 테이블 생성
     * @param {Array} results - 결과 데이터
     * @param {number} rowCount - 행 수
     * @param {number} executionTime - 실행 시간
     * @returns {string} HTML 테이블
     */
    createResultsTable(results, rowCount, executionTime) {
        if (!results || results.length === 0) return '';

        const columns = Object.keys(results[0]);
        const headerRow = columns.map(col => 
            `<th class="px-3 py-2 text-left font-semibold text-sm text-gray-700 bg-gray-50 border-b border-gray-200">${this.escapeHtml(col)}</th>`
        ).join('');
        
        const dataRows = results.map(row => {
            const cells = columns.map(col => {
                const value = row[col];
                const displayValue = this.formatCellValue(value);
                return `<td class="px-3 py-2 text-sm border-b border-gray-100 max-w-xs truncate" title="${this.escapeHtml(String(value || ''))}">${displayValue}</td>`;
            }).join('');
            return `<tr class="hover:bg-gray-50">${cells}</tr>`;
        }).join('');

        return `
            <div class="border border-gray-200 rounded-lg overflow-hidden mb-4">
                <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
                    <span class="font-semibold text-gray-700">조회 결과</span>
                    <div class="text-sm text-gray-500">
                        ${rowCount.toLocaleString()}행${executionTime ? ` · ${executionTime}ms` : ''}
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead><tr>${headerRow}</tr></thead>
                        <tbody>${dataRows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    /**
     * 셀 값 포맷팅
     * @param {any} value - 셀 값
     * @returns {string} 포맷된 HTML
     */
    formatCellValue(value) {
        if (value === null || value === undefined) {
            return '<em class="text-gray-400">null</em>';
        }
        
        const stringValue = String(value);
        if (stringValue.length > 50) {
            return this.escapeHtml(stringValue.substring(0, 47) + '...');
        }
        
        return this.escapeHtml(stringValue);
    }

    /**
     * 마크다운 포맷팅
     * @param {string} text - 마크다운 텍스트
     * @returns {string} HTML
     */
    formatMarkdown(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm">$1</code>')
            .replace(/\n\n/g, '</p><p class="mb-4">')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p class="mb-4">')
            .replace(/$/, '</p>');
    }

    /**
     * 웰컴 메시지 숨기기
     */
    hideWelcomeMessage() {
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.transition = 'opacity 0.5s ease';
            welcomeMessage.style.opacity = '0';
            setTimeout(() => {
                welcomeMessage.style.display = 'none';
            }, 500);
        }
    }

    /**
     * 복원 알림 표시
     * @param {number} messageCount - 복원된 메시지 수
     */
    showRestoreNotification(messageCount) {
        const notification = document.createElement('div');
        notification.className = 'bg-blue-50 border border-blue-200 border-l-4 border-l-blue-500 text-blue-700 p-3 rounded-lg mb-4 flex items-center justify-between';
        notification.innerHTML = `
            <span class="flex items-center">
                <span class="mr-2">💾</span>
                이전 대화를 복원했습니다 (${messageCount.toLocaleString()}개 메시지)
            </span>
            <button onclick="this.parentElement.remove()" class="text-blue-500 hover:text-blue-700 p-1 rounded">✕</button>
        `;
        
        // 접근성 속성
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'polite');
        
        this.elements.conversationArea?.insertBefore(notification, this.elements.conversationArea.firstChild);
        
        // 자동 제거
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.transition = 'opacity 0.5s ease';
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 500);
            }
        }, 5000);
    }

    /**
     * 대화창 하단으로 스크롤
     */
    scrollToBottom() {
        setTimeout(() => {
            const container = this.elements.conversationArea?.parentElement;
            if (container) {
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }, 100);
    }

    /**
     * HTML 이스케이프
     * @param {string} text - 이스케이프할 텍스트
     * @returns {string} 이스케이프된 텍스트
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 이벤트 리스너 추가 (메모리 누수 방지)
     * @param {Element|Window} element - 이벤트 대상
     * @param {string} event - 이벤트 타입
     * @param {Function} handler - 이벤트 핸들러
     */
    addEventListener(element, event, handler) {
        element.addEventListener(event, handler);
        
        // 리스너 추적 (정리용)
        if (!this.eventListeners.has(element)) {
            this.eventListeners.set(element, []);
        }
        this.eventListeners.get(element).push({ event, handler });
    }

    /**
     * 커스텀 이벤트 발생
     * @param {string} eventName - 이벤트 이름
     * @param {Object} detail - 이벤트 데이터
     */
    dispatchCustomEvent(eventName, detail = {}) {
        const event = new CustomEvent(eventName, {
            detail,
            bubbles: true,
            cancelable: true
        });
        
        document.dispatchEvent(event);
    }

    /**
     * 디바운스 유틸리티
     * @param {Function} func - 실행할 함수
     * @param {number} wait - 대기 시간
     * @returns {Function} 디바운스된 함수
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * 쓰로틀 유틸리티
     * @param {Function} func - 실행할 함수
     * @param {number} limit - 제한 시간
     * @returns {Function} 쓰로틀된 함수
     */
    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * 모든 이벤트 리스너 정리 (메모리 누수 방지)
     */
    cleanup() {
        this.eventListeners.forEach((listeners, element) => {
            listeners.forEach(({ event, handler }) => {
                element.removeEventListener(event, handler);
            });
        });
        
        this.eventListeners.clear();
        console.log('🧹 UI 관리자 정리 완료');
    }

    /**
     * 상태 정보 반환
     * @returns {Object} UI 상태 정보
     */
    getState() {
        return {
            hasInput: this.getInputValue().length > 0,
            isComposing: this.isComposing,
            messageCount: document.querySelectorAll('.message').length,
            eventListenerCount: Array.from(this.eventListeners.values())
                .reduce((total, listeners) => total + listeners.length, 0)
        };
    }
}