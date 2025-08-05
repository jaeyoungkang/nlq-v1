/**
 * 대화 세션 저장 관리 모듈 (ES6 모듈)
 * 책임: localStorage 기반 대화 세션 관리
 */

export class ConversationStorage {
    constructor() {
        this.currentSessionId = null;
        this.STORAGE_KEYS = {
            CURRENT_SESSION: 'bq_assistant_current_session',
            SESSION_PREFIX: 'bq_session_'
        };
        this.MAX_SESSIONS = 10; // 최대 세션 수 제한
        this.init();
    }

    /**
     * 저장소 초기화
     */
    init() {
        this.loadCurrentSession();
        this.cleanupOldSessions();
    }

    /**
     * 새 세션 생성
     * @returns {Object} 생성된 세션 객체
     */
    createNewSession() {
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
        const session = {
            sessionId,
            createdAt: new Date().toISOString(),
            lastUpdated: new Date().toISOString(),
            messages: [],
            metadata: {
                userAgent: navigator.userAgent,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                language: navigator.language
            },
            settings: {
                maxMessages: 50,
                autoSave: true,
                theme: 'default'
            }
        };

        this.currentSessionId = sessionId;
        this._saveSession(session);
        
        console.log(`📝 새 세션 생성: ${sessionId}`);
        return session;
    }

    /**
     * 메시지 저장
     * @param {Object} message - 저장할 메시지 객체
     * @returns {Object|null} 저장된 메시지 (ID 포함)
     */
    saveMessage(message) {
        if (!this.currentSessionId) {
            this.createNewSession();
        }

        try {
            const session = this.getCurrentSession();
            if (!session) {
                console.error('❌ 세션을 찾을 수 없습니다');
                return null;
            }

            const messageWithId = {
                id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                ...message,
                timestamp: message.timestamp || new Date().toISOString(),
                sessionId: this.currentSessionId
            };

            session.messages.push(messageWithId);
            session.lastUpdated = new Date().toISOString();

            // 메시지 수 제한 적용
            if (session.messages.length > session.settings.maxMessages) {
                const removedCount = session.messages.length - session.settings.maxMessages;
                session.messages = session.messages.slice(-session.settings.maxMessages);
                console.log(`🗑️ 오래된 메시지 ${removedCount}개 제거`);
            }

            this._saveSession(session);
            
            console.log(`💾 메시지 저장 완료: ${messageWithId.id}`);
            return messageWithId;
            
        } catch (error) {
            console.error('❌ 메시지 저장 실패:', error);
            return null;
        }
    }

    /**
     * 현재 세션 로드
     * @returns {Object|null} 세션 객체 또는 null
     */
    loadCurrentSession() {
        try {
            const sessionData = localStorage.getItem(this.STORAGE_KEYS.CURRENT_SESSION);
            if (sessionData) {
                const session = JSON.parse(sessionData);
                this.currentSessionId = session.sessionId;
                console.log(`📂 세션 로드: ${session.sessionId} (메시지 ${session.messages.length}개)`);
                return session;
            }
        } catch (error) {
            console.error('❌ 세션 로드 실패:', error);
            this._clearCorruptedSession();
        }
        return null;
    }

    /**
     * 현재 세션 가져오기
     * @returns {Object|null} 현재 세션 객체
     */
    getCurrentSession() {
        return this.loadCurrentSession();
    }

    /**
     * 현재 세션 삭제
     */
    clearCurrentSession() {
        try {
            if (this.currentSessionId) {
                localStorage.removeItem(this.STORAGE_KEYS.CURRENT_SESSION);
                console.log(`🗑️ 세션 삭제: ${this.currentSessionId}`);
                this.currentSessionId = null;
            }
        } catch (error) {
            console.error('❌ 세션 삭제 실패:', error);
        }
    }

    /**
     * 모든 세션 목록 조회
     * @returns {Array} 세션 목록
     */
    getAllSessions() {
        const sessions = [];
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith(this.STORAGE_KEYS.SESSION_PREFIX)) {
                    const sessionData = localStorage.getItem(key);
                    if (sessionData) {
                        const session = JSON.parse(sessionData);
                        sessions.push({
                            sessionId: session.sessionId,
                            createdAt: session.createdAt,
                            lastUpdated: session.lastUpdated,
                            messageCount: session.messages.length
                        });
                    }
                }
            }
        } catch (error) {
            console.error('❌ 세션 목록 조회 실패:', error);
        }
        
        return sessions.sort((a, b) => new Date(b.lastUpdated) - new Date(a.lastUpdated));
    }

    /**
     * 특정 세션 삭제
     * @param {string} sessionId - 삭제할 세션 ID
     */
    deleteSession(sessionId) {
        try {
            const sessionKey = `${this.STORAGE_KEYS.SESSION_PREFIX}${sessionId}`;
            localStorage.removeItem(sessionKey);
            
            // 현재 세션이면 현재 세션도 클리어
            if (this.currentSessionId === sessionId) {
                this.clearCurrentSession();
            }
            
            console.log(`🗑️ 세션 삭제 완료: ${sessionId}`);
        } catch (error) {
            console.error('❌ 세션 삭제 실패:', error);
        }
    }

    /**
     * 저장소 사용량 조회
     * @returns {Object} 사용량 정보
     */
    getStorageInfo() {
        try {
            const used = new Blob(Object.values(localStorage)).size;
            const quota = 5 * 1024 * 1024; // 5MB (일반적인 localStorage 제한)
            
            return {
                used,
                quota,
                usagePercent: Math.round((used / quota) * 100),
                sessionCount: this.getAllSessions().length,
                currentSessionId: this.currentSessionId
            };
        } catch (error) {
            console.error('❌ 저장소 정보 조회 실패:', error);
            return { used: 0, quota: 0, usagePercent: 0, sessionCount: 0 };
        }
    }

    /**
     * 오래된 세션 정리
     * @private
     */
    cleanupOldSessions() {
        try {
            const sessions = this.getAllSessions();
            
            // 최대 세션 수 초과 시 오래된 것부터 삭제
            if (sessions.length > this.MAX_SESSIONS) {
                const sessionsToDelete = sessions.slice(this.MAX_SESSIONS);
                sessionsToDelete.forEach(session => {
                    this.deleteSession(session.sessionId);
                });
                console.log(`🧹 오래된 세션 ${sessionsToDelete.length}개 정리 완료`);
            }

            // 30일 이상 된 세션 삭제
            const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
            const expiredSessions = sessions.filter(session => 
                new Date(session.lastUpdated) < thirtyDaysAgo
            );
            
            expiredSessions.forEach(session => {
                this.deleteSession(session.sessionId);
            });
            
            if (expiredSessions.length > 0) {
                console.log(`🧹 만료된 세션 ${expiredSessions.length}개 정리 완료`);
            }
            
        } catch (error) {
            console.error('❌ 세션 정리 실패:', error);
        }
    }

    /**
     * 세션을 localStorage에 저장
     * @param {Object} session - 저장할 세션 객체
     * @private
     */
    _saveSession(session) {
        try {
            // 현재 세션으로 설정
            localStorage.setItem(this.STORAGE_KEYS.CURRENT_SESSION, JSON.stringify(session));
            
            // 개별 세션으로도 저장 (히스토리 관리용)
            const sessionKey = `${this.STORAGE_KEYS.SESSION_PREFIX}${session.sessionId}`;
            localStorage.setItem(sessionKey, JSON.stringify(session));
            
        } catch (error) {
            console.error('❌ 세션 저장 실패:', error);
            
            // 저장 공간 부족 시 오래된 세션 정리 후 재시도
            if (error.name === 'QuotaExceededError') {
                console.log('💾 저장 공간 부족, 오래된 세션 정리 중...');
                this.cleanupOldSessions();
                
                try {
                    localStorage.setItem(this.STORAGE_KEYS.CURRENT_SESSION, JSON.stringify(session));
                    console.log('✅ 정리 후 세션 저장 성공');
                } catch (retryError) {
                    console.error('❌ 재시도 후에도 저장 실패:', retryError);
                }
            }
        }
    }

    /**
     * 손상된 세션 데이터 정리
     * @private
     */
    _clearCorruptedSession() {
        try {
            localStorage.removeItem(this.STORAGE_KEYS.CURRENT_SESSION);
            console.log('🔧 손상된 세션 데이터 정리 완료');
        } catch (error) {
            console.error('❌ 손상된 세션 정리 실패:', error);
        }
    }

    /**
     * 세션 데이터 내보내기 (백업용)
     * @returns {string} JSON 형태의 세션 데이터
     */
    exportSessionData() {
        try {
            const currentSession = this.getCurrentSession();
            if (currentSession) {
                return JSON.stringify(currentSession, null, 2);
            }
            return null;
        } catch (error) {
            console.error('❌ 세션 데이터 내보내기 실패:', error);
            return null;
        }
    }

    /**
     * 세션 데이터 가져오기 (복원용)
     * @param {string} jsonData - JSON 형태의 세션 데이터
     * @returns {boolean} 성공 여부
     */
    importSessionData(jsonData) {
        try {
            const sessionData = JSON.parse(jsonData);
            
            // 세션 데이터 유효성 검증
            if (!sessionData.sessionId || !Array.isArray(sessionData.messages)) {
                throw new Error('유효하지 않은 세션 데이터 형식');
            }
            
            // 새 세션 ID 생성 (중복 방지)
            sessionData.sessionId = `imported_${Date.now()}`;
            sessionData.lastUpdated = new Date().toISOString();
            
            this.currentSessionId = sessionData.sessionId;
            this._saveSession(sessionData);
            
            console.log('✅ 세션 데이터 가져오기 성공');
            return true;
            
        } catch (error) {
            console.error('❌ 세션 데이터 가져오기 실패:', error);
            return false;
        }
    }
}