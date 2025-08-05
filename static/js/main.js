/**
 * BigQuery AI Assistant - Unified JavaScript File with Google Authentication
 * This single file handles all client-side logic including API calls,
 * UI updates, authentication, and session management.
 */
const app = {
    // A central place to store references to key DOM elements.
    elements: {},
    // A flag to prevent multiple submissions while a request is in progress.
    isProcessing: false,
    // A simple object to hold the conversation history for the current session.
    session: { messages: [] },
    // Authentication state
    auth: {
        isAuthenticated: false,
        user: null,
        accessToken: null,
        refreshToken: null
    },
    // Usage tracking for guest users
    usage: {
        remaining: 10,
        limit: 10,
        canUse: true
    },

    /**
     * Initializes the application.
     * Caches DOM elements, loads the session, and binds event listeners.
     */
    init() {
        this.elements = {
            // Existing elements
            queryForm: document.getElementById('queryForm'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            conversationArea: document.getElementById('conversationArea'),
            sampleButtons: document.getElementById('sampleButtons'),
            
            // Authentication elements
            authSection: document.getElementById('authSection'),
            authLoading: document.getElementById('authLoading'),
            guestState: document.getElementById('guestState'),
            authenticatedState: document.getElementById('authenticatedState'),
            googleSignInButton: document.getElementById('googleSignInButton'),
            logoutButton: document.getElementById('logoutButton'),
            
            // User info elements
            userAvatar: document.getElementById('userAvatar'),
            userName: document.getElementById('userName'),
            userEmail: document.getElementById('userEmail'),
            
            // Usage elements
            usageLimitWarning: document.getElementById('usageLimitWarning'),
            warningText: document.getElementById('warningText'),
            statusBar: document.getElementById('statusBar'),
            statusText: document.getElementById('statusText')
        };
        
        this.loadSession();
        this.bindEvents();
        this.initAuth();
    },

    /**
     * Initialize authentication system
     */
    async initAuth() {
        // 초기 상태: 로딩 표시
        this.showAuthLoading(true);
        
        try {
            // Load stored tokens
            this.loadStoredTokens();
            
            // Initialize Google Sign-In
            await this.initGoogleSignIn();
            
            // Verify current authentication state
            await this.verifyAuthState();
            
        } catch (error) {
            console.error('Authentication initialization failed:', error);
            this.showGuestState();
        } finally {
            this.showAuthLoading(false);
        }
    },

    /**
     * Initialize Google Sign-In
     */
    async initGoogleSignIn() {
        return new Promise((resolve, reject) => {
            if (typeof google === 'undefined') {
                reject(new Error('Google SDK not loaded'));
                return;
            }

            try {
                google.accounts.id.initialize({
                    client_id: this.getGoogleClientId(),
                    callback: this.handleGoogleSignIn.bind(this),
                    auto_select: false,
                    cancel_on_tap_outside: false
                });

                // Render the sign-in button
                google.accounts.id.renderButton(
                    this.elements.googleSignInButton,
                    {
                        theme: 'outline',
                        size: 'medium',
                        text: 'signin_with',
                        shape: 'rectangular',
                        logo_alignment: 'left'
                    }
                );

                resolve();
            } catch (error) {
                reject(error);
            }
        });
    },

    /**
     * Get Google Client ID from environment or configuration
     */
    getGoogleClientId() {
        // In a real implementation, this should come from your server
        // For now, we'll need to configure this based on your environment
        return window.GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID_HERE';
    },

    /**
     * Handle Google Sign-In response
     */
    async handleGoogleSignIn(response) {
        try {
            this.showAuthLoading(true);
            
            // Send the ID token to your backend
            const result = await this.sendApiRequest('/api/auth/google-login', {
                method: 'POST',
                body: JSON.stringify({ id_token: response.credential })
            });

            if (result.success) {
                // Store tokens
                this.auth.accessToken = result.access_token;
                this.auth.refreshToken = result.refresh_token;
                this.auth.user = result.user;
                this.auth.isAuthenticated = true;
                
                this.storeTokens();
                this.showAuthenticatedState();
                
                console.log('✅ Google Sign-In successful:', result.user.email);
            } else {
                throw new Error(result.error || 'Login failed');
            }
        } catch (error) {
            console.error('❌ Google Sign-In failed:', error);
            this.showError('로그인에 실패했습니다. 다시 시도해주세요.');
            this.showGuestState();
        } finally {
            this.showAuthLoading(false);
        }
    },

    /**
     * Handle logout
     */
    async handleLogout() {
        try {
            // Call logout API
            await this.sendApiRequest('/api/auth/logout', {
                method: 'POST'
            });
        } catch (error) {
            console.warn('Logout API call failed:', error);
        } finally {
            // Clear local state regardless of API result
            this.clearTokens();
            this.auth.isAuthenticated = false;
            this.auth.user = null;
            this.auth.accessToken = null;
            this.auth.refreshToken = null;
            
            // Sign out from Google
            if (typeof google !== 'undefined') {
                google.accounts.id.disableAutoSelect();
            }
            
            this.showGuestState();
            await this.updateUsageInfo();
            
            console.log('👋 Logged out successfully');
        }
    },

    /**
     * Verify current authentication state
     */
    async verifyAuthState() {
        try {
            const result = await this.sendApiRequest('/api/auth/verify', {
                method: 'GET'
            });

            if (result.success) {
                if (result.authenticated && result.user) {
                    // User is authenticated
                    this.auth.isAuthenticated = true;
                    this.auth.user = result.user;
                    this.showAuthenticatedState();
                } else {
                    // User is not authenticated, update usage info
                    this.auth.isAuthenticated = false;
                    this.auth.user = null;
                    if (result.usage) {
                        this.updateUsageDisplay(result.usage);
                    }
                    this.showGuestState();
                }
            } else {
                throw new Error(result.error || 'Verification failed');
            }
        } catch (error) {
            console.warn('Auth verification failed:', error);
            // Clear auth state and show guest
            this.auth.isAuthenticated = false;
            this.auth.user = null;
            
            // Try to refresh token if we have one
            if (this.auth.refreshToken) {
                await this.attemptTokenRefresh();
            } else {
                this.showGuestState();
                await this.updateUsageInfo();
            }
        }
    },

    /**
     * Attempt to refresh access token
     */
    async attemptTokenRefresh() {
        try {
            const result = await this.sendApiRequest('/api/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: this.auth.refreshToken })
            });

            if (result.success) {
                this.auth.accessToken = result.access_token;
                this.auth.user = result.user;
                this.auth.isAuthenticated = true;
                this.storeTokens();
                this.showAuthenticatedState();
                console.log('🔄 Token refreshed successfully');
            } else {
                throw new Error(result.error || 'Token refresh failed');
            }
        } catch (error) {
            console.warn('Token refresh failed:', error);
            // Clear everything and show guest state
            this.clearTokens();
            this.auth.isAuthenticated = false;
            this.auth.user = null;
            this.auth.accessToken = null;
            this.auth.refreshToken = null;
            this.showGuestState();
            await this.updateUsageInfo();
        }
    },

    /**
     * Update usage information for guest users
     */
    async updateUsageInfo() {
        if (this.auth.isAuthenticated) return;

        try {
            const result = await this.sendApiRequest('/api/auth/usage', {
                method: 'GET'
            });

            if (result.success && result.usage) {
                this.updateUsageDisplay(result.usage);
            }
        } catch (error) {
            console.warn('Failed to update usage info:', error);
        }
    },

    /**
     * Update usage display elements
     */
    updateUsageDisplay(usage) {
        this.usage = usage;
        
        if (this.elements.statusText) {
            this.elements.statusText.textContent = usage.message || `남은 횟수: ${usage.remaining || 0}회`;
        }
        
        // Show/hide warning
        const shouldShowWarning = !usage.can_use;
        this.elements.usageLimitWarning?.classList.toggle('hidden', !shouldShowWarning);
        
        if (shouldShowWarning && this.elements.warningText) {
            this.elements.warningText.textContent = usage.message || '일일 사용 제한에 도달했습니다.';
        }
        
        // Disable send button if limit reached
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = !usage.can_use || this.isProcessing;
        }
    },

    /**
     * Store tokens in localStorage
     */
    storeTokens() {
        if (this.auth.accessToken) {
            localStorage.setItem('bq_access_token', this.auth.accessToken);
        }
        if (this.auth.refreshToken) {
            localStorage.setItem('bq_refresh_token', this.auth.refreshToken);
        }
        if (this.auth.user) {
            localStorage.setItem('bq_user', JSON.stringify(this.auth.user));
        }
    },

    /**
     * Load stored tokens from localStorage
     */
    loadStoredTokens() {
        this.auth.accessToken = localStorage.getItem('bq_access_token');
        this.auth.refreshToken = localStorage.getItem('bq_refresh_token');
        const userStr = localStorage.getItem('bq_user');
        if (userStr) {
            try {
                this.auth.user = JSON.parse(userStr);
            } catch (e) {
                console.warn('Failed to parse stored user:', e);
            }
        }
    },

    /**
     * Clear stored tokens
     */
    clearTokens() {
        localStorage.removeItem('bq_access_token');
        localStorage.removeItem('bq_refresh_token');
        localStorage.removeItem('bq_user');
    },

    /**
     * Show authentication loading state
     */
    showAuthLoading(show) {
        if (show) {
            // 로딩 중일 때: 로딩만 표시, 나머지는 숨김
            this.elements.authLoading?.classList.remove('hidden');
            this.elements.guestState?.classList.add('hidden');
            this.elements.authenticatedState?.classList.add('hidden');
        } else {
            // 로딩 완료: 로딩은 숨김 (다른 상태는 각각의 show 함수에서 처리)
            this.elements.authLoading?.classList.add('hidden');
        }
    },

    /**
     * Show guest user state
     */
    showGuestState() {
        this.elements.authLoading?.classList.add('hidden');
        this.elements.guestState?.classList.remove('hidden');
        this.elements.authenticatedState?.classList.add('hidden');
        this.elements.statusBar?.classList.remove('hidden');
    },

    /**
     * Show authenticated user state
     */
    showAuthenticatedState() {
        this.elements.authLoading?.classList.add('hidden');
        this.elements.guestState?.classList.add('hidden');
        this.elements.authenticatedState?.classList.remove('hidden');
        this.elements.statusBar?.classList.add('hidden');
        this.elements.usageLimitWarning?.classList.add('hidden');
        
        // Update user info
        if (this.auth.user) {
            if (this.elements.userName) {
                this.elements.userName.textContent = this.auth.user.name || 'User';
            }
            if (this.elements.userEmail) {
                this.elements.userEmail.textContent = this.auth.user.email || '';
            }
            if (this.elements.userAvatar && this.auth.user.picture) {
                this.elements.userAvatar.src = this.auth.user.picture;
                this.elements.userAvatar.classList.remove('hidden');
            }
        }
        
        // Enable send button for authenticated users
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = this.isProcessing;
        }
    },

    /**
     * Show error message
     */
    showError(message) {
        // Simple error display - you can enhance this
        alert(message);
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

        // Logout button
        this.elements.logoutButton?.addEventListener('click', () => {
            this.handleLogout();
        });
    },

    /**
     * Handles the message submission process.
     * @param {string} message - The user's input message.
     */
    async handleMessageSubmit(message) {
        if (this.isProcessing || !message.trim()) return;
        
        // Check usage limit for guest users
        if (!this.auth.isAuthenticated && !this.usage.can_use) {
            this.showError('일일 사용 제한에 도달했습니다. 구글 로그인하여 무제한으로 이용하세요!');
            return;
        }
        
        this.isProcessing = true;
        this.elements.sendButton.disabled = true;

        this.addMessage('user', this.escapeHTML(message));
        this.saveMessage({ type: 'user', content: message });
        this.elements.messageInput.value = '';

        const loadingId = this.addLoadingMessage();

        try {
            const response = await this.sendApiRequest('/api/chat', {
                method: 'POST',
                body: JSON.stringify({ message })
            });
            
            this.removeMessage(loadingId);
            this.handleApiResponse(response);
            
            // Update usage info for guest users
            if (!this.auth.isAuthenticated && response.usage) {
                this.updateUsageDisplay(response.usage);
            }
        } catch (error) {
            this.removeMessage(loadingId);
            this.addMessage('assistant', `<span class="text-red-500">오류: ${this.escapeHTML(error.message)}</span>`);
        } finally {
            this.isProcessing = false;
            // Only enable button if user can use the service
            this.elements.sendButton.disabled = !this.auth.isAuthenticated && !this.usage.can_use;
        }
    },

    /**
     * Sends a request to the backend API with authentication.
     * @param {string} endpoint - The API endpoint.
     * @param {Object} options - Fetch options.
     * @returns {Promise<Object>} - The JSON response from the server.
     */
    async sendApiRequest(endpoint, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        };
        
        // Merge options
        const mergedOptions = { ...defaultOptions, ...options };
        
        // Add authorization header if authenticated
        if (this.auth.isAuthenticated && this.auth.accessToken) {
            mergedOptions.headers.Authorization = `Bearer ${this.auth.accessToken}`;
        }
        
        const response = await fetch(endpoint, mergedOptions);
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
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
            if (result.generated_sql) {
                const escapedSql = this.escapeHTML(result.generated_sql);
                content += `
                    <div class="mb-2">
                        <p class="font-bold text-sm text-gray-600">생성된 SQL</p>
                        <pre class="bg-gray-100 p-2 rounded-md text-xs text-gray-800 whitespace-pre-wrap font-mono"><code>${escapedSql}</code></pre>
                    </div>
                `;
            }
            if (result.data && result.data.length > 0) {
                content += this.createResultsTable(result.data, result.row_count);
            } else if (result.generated_sql) {
                content += '<p>조회 결과가 없습니다.</p>';
            } else {
                content = '결과를 표시할 수 없습니다.';
            }
        } else {
            content = this.escapeHTML(result.content || result.analysis || result.response || '결과를 표시할 수 없습니다.');
        }
        
        this.addMessage('assistant', content);
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