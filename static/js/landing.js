// 랜딩 페이지 인터랙션 관리
class LandingPageManager {
    constructor() {
        this.currentScenario = 'basic';
        this.demoScenarios = {
            basic: {
                title: '📊 기본 조회',
                messages: [
                    {
                        type: 'user',
                        content: '상위 10개 레코드를 조회해주세요'
                    },
                    {
                        type: 'assistant',
                        content: this.createSQLDemo('SELECT * FROM `nlq-ex.test_dataset.events_20210131` LIMIT 10;', '10행 조회 완료'),
                        delay: 1500
                    }
                ]
            },
            analysis: {
                title: '🤖 AI 분석',
                messages: [
                    {
                        type: 'user',
                        content: '시간대별 이벤트 분포를 분석해주세요'
                    },
                    {
                        type: 'assistant',
                        content: this.createSQLDemo(
                            'SELECT EXTRACT(HOUR FROM event_timestamp) as hour, COUNT(*) as event_count FROM `nlq-ex.test_dataset.events_20210131` GROUP BY hour ORDER BY hour;',
                            '24시간 분포 데이터'
                        ),
                        delay: 2000
                    },
                    {
                        type: 'assistant',
                        content: this.createAnalysisDemo('🤖 분석 결과: 오후 2-4시에 가장 많은 활동이 발생하며, 새벽 시간대는 활동이 현저히 줄어듭니다. 사용자들의 업무 시간과 일치하는 패턴을 보입니다.'),
                        delay: 3500
                    }
                ]
            },
            complex: {
                title: '🔍 복합 쿼리',
                messages: [
                    {
                        type: 'user',
                        content: '카테고리별 이벤트 수와 고유 사용자 수를 함께 보여주세요'
                    },
                    {
                        type: 'assistant',
                        content: this.createSQLDemo(
                            'SELECT category, COUNT(*) as total_events, COUNT(DISTINCT user_id) as unique_users FROM `nlq-ex.test_dataset.events_20210131` GROUP BY category ORDER BY total_events DESC;',
                            '카테고리별 복합 통계'
                        ),
                        delay: 2500
                    }
                ]
            }
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.showScenario(this.currentScenario);
        this.setupScrollAnimations();
        this.setupNavigationScroll();
    }

    bindEvents() {
        // 시나리오 버튼 이벤트
        document.querySelectorAll('.scenario-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const scenario = e.target.dataset.scenario;
                this.switchScenario(scenario);
            });
        });

        // 모바일 메뉴 토글
        const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
        const navLinks = document.querySelector('.nav-links');
        
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => {
                navLinks.classList.toggle('mobile-open');
            });
        }

        // 네비게이션 스크롤 효과
        window.addEventListener('scroll', this.handleNavScroll.bind(this));
    }

    switchScenario(scenario) {
        if (this.currentScenario === scenario) return;
        
        this.currentScenario = scenario;
        
        // 버튼 상태 업데이트
        document.querySelectorAll('.scenario-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.scenario === scenario) {
                btn.classList.add('active');
            }
        });

        // 시나리오 표시
        this.showScenario(scenario);
    }

    showScenario(scenario) {
        const demoMessages = document.getElementById('demoMessages');
        const scenarioData = this.demoScenarios[scenario];
        
        if (!demoMessages || !scenarioData) return;

        // 메시지 컨테이너 초기화
        demoMessages.innerHTML = '';
        demoMessages.style.opacity = '0';
        
        // 페이드 인 효과
        setTimeout(() => {
            demoMessages.style.opacity = '1';
            this.animateMessages(scenarioData.messages, demoMessages);
        }, 200);
    }

    animateMessages(messages, container) {
        messages.forEach((message, index) => {
            setTimeout(() => {
                this.addDemoMessage(message, container);
            }, message.delay || index * 800);
        });
    }

    addDemoMessage(message, container) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `demo-message ${message.type}-message`;
        
        if (message.type === 'user') {
            messageDiv.innerHTML = `
                <div class="demo-user-msg">
                    <div class="msg-bubble user-bubble">
                        ${message.content}
                    </div>
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="demo-ai-msg">
                    <div class="msg-bubble ai-bubble">
                        ${message.content}
                    </div>
                </div>
            `;
        }

        // 타이핑 애니메이션 효과
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';
        container.appendChild(messageDiv);

        // 애니메이션 시작
        setTimeout(() => {
            messageDiv.style.transition = 'all 0.5s ease';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }, 100);

        // 스크롤 조정
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 150);
    }

    createSQLDemo(sql, resultText) {
        return `
            <div class="demo-sql-block">
                <div class="demo-sql-header">생성된 SQL</div>
                <div class="demo-sql-content">${this.escapeHtml(sql)}</div>
            </div>
            <div class="demo-results">
                <div class="demo-results-header">📊 조회 결과</div>
                <div class="demo-results-content">${resultText}</div>
            </div>
        `;
    }

    createAnalysisDemo(analysisText) {
        return `
            <div class="demo-analysis">
                <div class="demo-analysis-header">AI 분석 결과</div>
                <div class="demo-analysis-content">${analysisText}</div>
            </div>
        `;
    }

    setupScrollAnimations() {
        // Intersection Observer로 스크롤 애니메이션
        const animationTargets = document.querySelectorAll('.feature-card, .use-case-card, .section-header');
        
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);

        animationTargets.forEach(target => {
            target.style.opacity = '0';
            target.style.transform = 'translateY(30px)';
            target.style.transition = 'all 0.6s ease';
            observer.observe(target);
        });
    }

    setupNavigationScroll() {
        // 네비게이션 링크 부드러운 스크롤
        document.querySelectorAll('a[href^="#"]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                
                if (targetElement) {
                    const offsetTop = targetElement.offsetTop - 80; // 네비게이션 높이 고려
                    window.scrollTo({
                        top: offsetTop,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    handleNavScroll() {
        const nav = document.querySelector('.navigation');
        const scrolled = window.scrollY > 50;
        
        if (scrolled) {
            nav.style.background = 'rgba(255, 255, 255, 0.98)';
            nav.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        } else {
            nav.style.background = 'rgba(255, 255, 255, 0.95)';
            nav.style.boxShadow = 'none';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 전역 함수들
function scrollToDemo() {
    const demoSection = document.getElementById('demo');
    if (demoSection) {
        const offsetTop = demoSection.offsetTop - 80;
        window.scrollTo({
            top: offsetTop,
            behavior: 'smooth'
        });
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    new LandingPageManager();
    
    // 추가 CSS 스타일을 동적으로 삽입
    const additionalStyles = `
        <style>
        /* 데모 메시지 스타일 */
        .demo-message {
            margin-bottom: 16px;
        }
        
        .demo-user-msg {
            display: flex;
            justify-content: flex-end;
        }
        
        .demo-ai-msg {
            display: flex;
            justify-content: flex-start;
        }
        
        .msg-bubble {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.5;
        }
        
        .user-bubble {
            background: #d97706;
            color: white;
            border-bottom-right-radius: 4px;
        }
        
        .ai-bubble {
            background: white;
            border: 1px solid #e5e7eb;
            border-bottom-left-radius: 4px;
            color: #374151;
        }
        
        .demo-sql-block {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.8rem;
        }
        
        .demo-sql-header {
            font-size: 0.7rem;
            font-weight: 600;
            color: #6b7280;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .demo-sql-content {
            color: #374151;
            white-space: pre-wrap;
        }
        
        .demo-results {
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
        }
        
        .demo-results-header {
            font-size: 0.8rem;
            font-weight: 600;
            color: #0ea5e9;
            margin-bottom: 6px;
        }
        
        .demo-results-content {
            color: #6b7280;
            font-size: 0.8rem;
        }
        
        .demo-analysis {
            background: #fef7ed;
            border: 1px solid #fed7aa;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
        }
        
        .demo-analysis-header {
            font-size: 0.8rem;
            font-weight: 600;
            color: #d97706;
            margin-bottom: 6px;
        }
        
        .demo-analysis-content {
            color: #92400e;
            font-size: 0.8rem;
            line-height: 1.5;
            font-style: italic;
        }
        
        /* 모바일 네비게이션 */
        @media (max-width: 768px) {
            .nav-links.mobile-open {
                display: flex;
                position: fixed;
                top: 70px;
                left: 0;
                right: 0;
                background: white;
                flex-direction: column;
                padding: 20px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                z-index: 999;
            }
            
            .nav-links.mobile-open a {
                padding: 12px 0;
                border-bottom: 1px solid #f3f4f6;
            }
            
            .nav-links.mobile-open a:last-child {
                border-bottom: none;
            }
        }
        
        /* 스크롤 애니메이션 */
        .fade-in-up {
            opacity: 0;
            transform: translateY(30px);
            transition: all 0.6s ease;
        }
        
        .fade-in-up.animate {
            opacity: 1;
            transform: translateY(0);
        }
        
        /* 히어로 섹션 배경 애니메이션 */
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-20px); }
        }
        
        .hero-visual .demo-preview {
            animation: float 6s ease-in-out infinite;
        }
        
        /* 기능 카드 호버 효과 강화 */
        .feature-card {
            position: relative;
            overflow: hidden;
        }
        
        .feature-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            transition: left 0.5s;
        }
        
        .feature-card:hover::after {
            left: 100%;
        }
        
        /* 통계 카운터 애니메이션 */
        .stat-number {
            display: inline-block;
        }
        
        .stat-number.counting {
            animation: pulse 0.5s ease-in-out;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        /* 데모 채팅 스크롤바 */
        .demo-chat::-webkit-scrollbar {
            width: 4px;
        }
        
        .demo-chat::-webkit-scrollbar-track {
            background: #f1f5f9;
        }
        
        .demo-chat::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 2px;
        }
        
        .demo-chat::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', additionalStyles);
});