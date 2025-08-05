/**
 * BigQuery AI Assistant - Unified JavaScript File
 * This single file handles all client-side logic including API calls,
 * UI updates, and session management.
 */
const app = {
    // A central place to store references to key DOM elements.
    elements: {},
    // A flag to prevent multiple submissions while a request is in progress.
    isProcessing: false,
    // A simple object to hold the conversation history for the current session.
    session: { messages: [] },

    /**
     * Initializes the application.
     * Caches DOM elements, loads the session, and binds event listeners.
     */
    init() {
        this.elements = {
            queryForm: document.getElementById('queryForm'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            conversationArea: document.getElementById('conversationArea'),
            sampleButtons: document.getElementById('sampleButtons'),
        };
        this.loadSession();
        this.bindEvents();
    },

    /**
     * Binds all necessary event listeners.
     */
    bindEvents() {
        this.elements.queryForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleMessageSubmit(this.elements.messageInput.value);
        });

        this.elements.sampleButtons.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') {
                this.handleMessageSubmit(e.target.textContent.trim());
            }
        });
    },

    /**
     * Handles the message submission process.
     * @param {string} message - The user's input message.
     */
    async handleMessageSubmit(message) {
        if (this.isProcessing || !message.trim()) return;
        this.isProcessing = true;
        this.elements.sendButton.disabled = true;

        this.addMessage('user', this.escapeHTML(message)); // Escape user message for safety
        this.saveMessage({ type: 'user', content: message }); // Save raw message
        this.elements.messageInput.value = '';

        const loadingId = this.addLoadingMessage();

        try {
            const response = await this.sendApiRequest(message);
            this.removeMessage(loadingId);
            this.handleApiResponse(response);
        } catch (error) {
            this.removeMessage(loadingId);
            this.addMessage('assistant', `<span class="text-red-500">오류: ${this.escapeHTML(error.message)}</span>`);
        } finally {
            this.isProcessing = false;
            this.elements.sendButton.disabled = false;
        }
    },

    /**
     * Sends a request to the backend API.
     * @param {string} message - The message to send.
     * @returns {Promise<Object>} - The JSON response from the server.
     */
    async sendApiRequest(message) {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || '서버 통신에 실패했습니다.');
        }
        return response.json();
    },

    /**
     * Processes the response from the API and updates the UI.
     * @param {Object} data - The API response data.
     */
    handleApiResponse(data) {
        const { result } = data;
        let content = '';

        if (result.type === 'query_result') {
            // Display the generated SQL if it exists
            if (result.generated_sql) {
                const escapedSql = this.escapeHTML(result.generated_sql);
                content += `
                    <div class="mb-2">
                        <p class="font-bold text-sm text-gray-600">생성된 SQL</p>
                        <pre class="bg-gray-100 p-2 rounded-md text-xs text-gray-800 whitespace-pre-wrap font-mono"><code>${escapedSql}</code></pre>
                    </div>
                `;
            }
            // Display the data table if it exists
            if (result.data && result.data.length > 0) {
                content += this.createResultsTable(result.data, result.row_count);
            } else if (result.generated_sql) {
                // If there was SQL but no data, show a message
                content += '<p>조회 결과가 없습니다.</p>';
            } else {
                // Fallback for query_result with no SQL and no data
                content = '결과를 표시할 수 없습니다.';
            }
        } else {
            // For other types like 'analysis' or 'guide'
            content = this.escapeHTML(result.analysis || result.response || '결과를 표시할 수 없습니다.');
        }
        
        this.addMessage('assistant', content);
        // Save the raw HTML content to localStorage to render it correctly on reload
        this.saveMessage({ type: 'assistant', content });
    },

    /**
     * Adds a message to the conversation UI.
     * @param {'user' | 'assistant'} type - The type of message.
     * @param {string} content - The HTML content of the message.
     * @param {string|null} id - An optional ID for the message element.
     */
    addMessage(type, content, id = null) {
        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.style.display = 'none';

        const messageDiv = document.createElement('div');
        if (id) messageDiv.id = id;
        messageDiv.className = `p-3 my-2 rounded-lg max-w-full break-words ${type === 'user' ? 'bg-amber-100 ml-auto' : 'bg-gray-100'}`;
        messageDiv.innerHTML = content;
        this.elements.conversationArea.appendChild(messageDiv);
        this.elements.conversationArea.scrollTop = this.elements.conversationArea.scrollHeight;
    },

    /**
     * Adds a temporary loading indicator to the UI.
     * @returns {string} The ID of the loading element.
     */
    addLoadingMessage() {
        const id = `loading-${Date.now()}`;
        const content = `
            <div class="flex items-center space-x-2">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>`;
        this.addMessage('assistant', content, id);
        return id;
    },

    /**
     * Removes an element from the UI by its ID.
     * @param {string} id - The ID of the element to remove.
     */
    removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    },

    /**
     * Creates an HTML table from query result data.
     * @param {Array<Object>} data - The array of data rows.
     * @param {number} rowCount - The total number of rows.
     * @returns {string} The HTML string for the table.
     */
    createResultsTable(data, rowCount) {
        const headers = Object.keys(data[0]).map(key => `<th class="p-2 border border-gray-300">${this.escapeHTML(key)}</th>`).join('');
        const rows = data.map(row => `<tr>${Object.values(row).map(val => `<td class="p-2 border border-gray-300">${this.escapeHTML(val)}</td>`).join('')}</tr>`).join('');
        return `
            <p class="font-bold mb-2">조회 결과 (${rowCount}행)</p>
            <div class="overflow-x-auto border rounded-md">
                <table class="w-full text-left text-sm whitespace-nowrap">
                    <thead class="bg-gray-100"><tr>${headers}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    },

    /**
     * Loads the session from localStorage and repopulates the UI.
     */
    loadSession() {
        try {
            const saved = localStorage.getItem('bq_session');
            if (saved) {
                this.session = JSON.parse(saved);
                // When loading, we pass the raw content to addMessage, which uses innerHTML.
                // This is safe because we save the already-processed/escaped HTML content.
                this.session.messages.forEach(msg => this.addMessage(msg.type, msg.content));
            }
        } catch (e) {
            console.error("세션 로딩 실패", e);
            this.session = { messages: [] };
        }
    },

    /**
     * Saves a message to the current session in localStorage.
     * @param {Object} message - The message object to save.
     */
    saveMessage(message) {
        this.session.messages.push(message);
        localStorage.setItem('bq_session', JSON.stringify(this.session));
    },

    /**
     * Escapes HTML special characters to prevent XSS.
     * @param {*} str - The value to escape.
     * @returns {string} - The escaped string.
     */
    escapeHTML(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
};

// Initialize the app once the DOM is fully loaded.
document.addEventListener('DOMContentLoaded', () => app.init());
