// 대화 세션 저장 관리 클래스
class ConversationStorage {
    constructor() {
        this.currentSessionId = null;
        this.STORAGE_KEYS = {
            CURRENT_SESSION: 'bq_assistant_current_session'
        };
        this.init();
    }

    init() {
        this.loadCurrentSession();
    }

    // 새 세션 생성
    createNewSession() {
        const sessionId = `session_${Date.now()}`;
        const session = {
            sessionId: sessionId,
            createdAt: new Date().toISOString(),
            lastUpdated: new Date().toISOString(),
            messages: [],
            settings: {
                maxMessages: 50,
                autoSave: true
            }
        };

        this.currentSessionId = sessionId;
        localStorage.setItem(this.STORAGE_KEYS.CURRENT_SESSION, JSON.stringify(session));
        
        return session;
    }

    // 메시지 저장
    saveMessage(message) {
        if (!this.currentSessionId) {
            this.createNewSession();
        }

        try {
            const session = this.getCurrentSession();
            if (!session) return;

            const messageWithId = {
                id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                ...message,
                timestamp: message.timestamp || new Date().toISOString()
            };

            session.messages.push(messageWithId);
            session.lastUpdated = new Date().toISOString();

            // 메시지 수 제한
            if (session.messages.length > session.settings.maxMessages) {
                session.messages = session.messages.slice(-session.settings.maxMessages);
            }

            localStorage.setItem(this.STORAGE_KEYS.CURRENT_SESSION, JSON.stringify(session));
            
            return messageWithId;
        } catch (error) {
            console.error('메시지 저장 실패:', error);
        }
    }

    // 현재 세션 로드
    loadCurrentSession() {
        try {
            const sessionData = localStorage.getItem(this.STORAGE_KEYS.CURRENT_SESSION);
            if (sessionData) {
                const session = JSON.parse(sessionData);
                this.currentSessionId = session.sessionId;
                return session;
            }
        } catch (error) {
            console.error('세션 로드 실패:', error);
        }
        return null;
    }

    // 현재 세션 가져오기
    getCurrentSession() {
        return this.loadCurrentSession();
    }

    // 현재 세션 삭제
    clearCurrentSession() {
        try {
            if (this.currentSessionId) {
                localStorage.removeItem(this.STORAGE_KEYS.CURRENT_SESSION);
                this.currentSessionId = null;
            }
        } catch (error) {
            console.error('세션 삭제 실패:', error);
        }
    }
}

class BigQueryAssistant {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.messageId = 0;
        this.isComposing = false;
        this.conversationHistory = [];
        
        // 대화 저장 기능 추가
        this.storage = new ConversationStorage();
        this.restoreSession();
    }

    initializeElements() {
        this.form = document.getElementById('queryForm');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.conversationArea = document.getElementById('conversationArea');
        this.sampleButtons = document.getElementById('sampleButtons');
    }

    bindEvents() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.messageInput.addEventListener('input', () => this.adjustTextareaHeight());
        this.messageInput.addEventListener('compositionstart', () => this.isComposing = true);
        this.messageInput.addEventListener('compositionend', () => this.isComposing = false);
        this.sampleButtons.addEventListener('click', (e) => this.handleSampleQuestion(e));
    }

    // 세션 복원
    restoreSession() {
        const session = this.storage.getCurrentSession();
        if (session && session.messages.length > 0) {
            this.restoreConversation(session.messages);
        }
    }

    // 대화 복원
    restoreConversation(messages) {
        // 웰컴 메시지 숨기기
        this.hideSampleQuestions();
        
        // 복원 알림 표시
        this.showRestoreNotification(messages.length);
        
        // 저장된 메시지들 복원
        messages.forEach(msg => {
            const messageDiv = this.createMessageElement(
                msg.type === 'user' ? 'user' : 'assistant',
                msg.type === 'user' ? 'User' : 'Assistant',
                msg.content
            );
            this.conversationArea.appendChild(messageDiv);
        });
        
        this.scrollToBottom();
    }

    // 복원 알림 표시
    showRestoreNotification(messageCount) {
        const notification = document.createElement('div');
        notification.className = 'restore-notification';
        notification.innerHTML = `
            💾 이전 대화를 복원했습니다 (${messageCount}개 메시지)
            <button onclick="this.parentElement.remove()">✕</button>
        `;
        
        this.conversationArea.insertBefore(notification, this.conversationArea.firstChild);
        
        // 5초 후 자동 제거
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey && !this.isComposing) {
            e.preventDefault();
            this.form.dispatchEvent(new Event('submit'));
        }
    }

    adjustTextareaHeight() {
        const textarea = this.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    handleSampleQuestion(e) {
        if (e.target.classList.contains('question-btn')) {
            this.messageInput.value = e.target.textContent;
            this.messageInput.focus();
            this.adjustTextareaHeight();
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        const message = this.messageInput.value.trim();
        if (!message) return;

        // 사용자 메시지 추가 및 저장
        this.addUserMessage(message);
        
        // 입력창 초기화
        this.messageInput.value = '';
        this.adjustTextareaHeight();
        
        // 로딩 메시지 추가
        const loadingId = this.addLoadingMessage();
        
        // 샘플 질문 숨기기 (첫 메시지 후)
        this.hideSampleQuestions();

        try {
            const context = this.buildContext();
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: message,
                    context: context
                })
            });

            const data = await response.json();
            
            // 로딩 메시지 제거
            this.removeMessage(loadingId);

            if (data.success) {
                this.handleChatResponse(data);
                this.updateConversationHistory(message, data);
            } else {
                this.addErrorMessage(data.error);
            }
        } catch (error) {
            this.removeMessage(loadingId);
            this.addErrorMessage(`네트워크 오류: ${error.message}`);
        }
    }

    addUserMessage(message) {
        const messageDiv = this.createMessageElement('user', 'User', message);
        this.conversationArea.appendChild(messageDiv);
        
        // 메시지 저장
        this.storage.saveMessage({
            type: 'user',
            content: message
        });
        
        this.scrollToBottom();
    }

    handleChatResponse(data) {
        const result = data.result;
        const category = data.category;
        
        let content = '';
        
        if (result.type === 'query_result') {
            // 쿼리 결과 처리 (기존 방식)
            if (result.generated_sql) {
                content += `<div class="sql-block">
                    <div class="sql-header">생성된 SQL</div>
                    <pre>${this.escapeHtml(result.generated_sql)}</pre>
                </div>`;
            }

            if (result.data && result.data.length > 0) {
                content += this.createResultsTable(result.data, result.row_count, data.execution_time_ms);
            } else if (result.data && result.data.length === 0) {
                content += '<p>조회 결과가 없습니다.</p>';
            }
        } else if (result.type === 'analysis') {
            // 데이터 분석 결과
            content = this.formatMarkdown(result.analysis);
        } else if (result.type === 'metadata') {
            // 메타데이터 응답
            content = this.formatMarkdown(result.response);
        } else if (result.type === 'guide') {
            // 가이드 응답
            content = this.formatMarkdown(result.guide);
        } else if (result.type === 'out_of_scope') {
            // 범위 외 응답
            content = this.formatMarkdown(result.response);
        } else if (result.type === 'error') {
            // 오류 처리
            content = `<div class="error-message">${this.escapeHtml(result.error)}</div>`;
        }

        const messageDiv = this.createMessageElement('assistant', 'Assistant', content);
        this.conversationArea.appendChild(messageDiv);
        
        // AI 응답 저장
        this.storage.saveMessage({
            type: 'assistant',
            content: content,
            metadata: {
                category: category,
                executionTime: data.execution_time_ms,
                hasResults: result.data ? result.data.length > 0 : false
            }
        });
        
        this.scrollToBottom();
    }

    buildContext() {
        // 최근 대화에서 컨텍스트 구성
        const recentHistory = this.conversationHistory.slice(-2); // 최근 2개만
        const context = {};
        
        // 가장 최근 쿼리 결과가 있으면 포함
        for (let i = recentHistory.length - 1; i >= 0; i--) {
            const item = recentHistory[i];
            if (item.type === 'query_result' && item.data) {
                context.previous_data = item.data.slice(0, 20); // 최대 20행만
                context.previous_sql = item.generated_sql;
                break;
            }
        }
        
        context.previous_queries = recentHistory.filter(h => h.type === 'query_result').length;
        
        return context;
    }

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
            timestamp: new Date().toISOString()
        };
        
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

    formatMarkdown(text) {
        // 간단한 마크다운 포맷팅
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    addErrorMessage(error) {
        const content = `<div class="error-message">${this.escapeHtml(error)}</div>`;
        const messageDiv = this.createMessageElement('assistant', 'Assistant', content);
        this.conversationArea.appendChild(messageDiv);
        
        // 에러 메시지도 저장
        this.storage.saveMessage({
            type: 'assistant',
            content: content,
            metadata: { isError: true }
        });
        
        this.scrollToBottom();
    }

    addLoadingMessage() {
        const loadingId = `loading-${++this.messageId}`;
        const content = `<div class="loading-message">
            <span>처리 중</span>
            <div class="loading-dots">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>`;
        
        const messageDiv = this.createMessageElement('assistant', 'Assistant', content, loadingId);
        this.conversationArea.appendChild(messageDiv);
        this.scrollToBottom();
        return loadingId;
    }

    removeMessage(messageId) {
        const messageElement = document.getElementById(messageId);
        if (messageElement) {
            messageElement.remove();
        }
    }

    createMessageElement(type, label, content, id = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        if (id) messageDiv.id = id;
        
        messageDiv.innerHTML = `
            <div class="message-label">${label}</div>
            <div class="message-content">${content}</div>
        `;
        
        return messageDiv;
    }

    createResultsTable(results, rowCount, executionTime) {
        if (!results || results.length === 0) return '';

        const columns = Object.keys(results[0]);
        
        const headerRow = columns.map(col => `<th>${this.escapeHtml(col)}</th>`).join('');
        
        const dataRows = results.map(row => {
            const cells = columns.map(col => {
                const value = row[col];
                const displayValue = this.formatCellValue(value);
                return `<td title="${this.escapeHtml(String(value || ''))}">${displayValue}</td>`;
            }).join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        return `
            <div class="results-table">
                <div class="results-header">
                    <span>조회 결과</span>
                    <div class="results-info">
                        ${rowCount}행 · ${executionTime}ms
                    </div>
                </div>
                <table class="data-table">
                    <thead><tr>${headerRow}</tr></thead>
                    <tbody>${dataRows}</tbody>
                </table>
            </div>
        `;
    }

    formatCellValue(value) {
        if (value === null || value === undefined) {
            return '<em style="color: #9ca3af;">null</em>';
        }
        
        const stringValue = String(value);
        if (stringValue.length > 50) {
            return this.escapeHtml(stringValue.substring(0, 47) + '...');
        }
        
        return this.escapeHtml(stringValue);
    }

    hideSampleQuestions() {
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            const container = document.querySelector('.conversation-container');
            container.scrollTop = container.scrollHeight;
        }, 100);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    new BigQueryAssistant();
});