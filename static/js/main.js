class BigQueryAssistant {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.messageId = 0;
        this.isComposing = false;
        this.conversationHistory = [];
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

        // 사용자 메시지 추가
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