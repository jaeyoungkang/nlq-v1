/**
 * 메인 진입점 - ES6 모듈 버전
 * BigQuery AI Assistant 앱 시작
 */

import { app } from './app-controller.js';

/**
 * DOM 로드 완료 후 앱 초기화
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log('🌟 BigQuery AI Assistant 시작');
        
        // 앱 초기화
        await app.init();
        
        // 접근성 개선 기능 활성화
        app.enhanceAccessibility();
        
        // 성능 모니터링 (개발 모드)
        if (window.location.hostname === 'localhost') {
            setTimeout(() => {
                console.log('📊 성능 메트릭:', app.getPerformanceMetrics());
            }, 2000);
        }
        
        console.log('🎉 BigQuery AI Assistant 준비 완료');
        
    } catch (error) {
        console.error('💥 앱 시작 실패:', error);
    }
});

/**
 * 서비스 워커 등록 (PWA 지원용 - 향후 확장)
 */
if ('serviceWorker' in navigator && window.location.protocol === 'https:') {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('🔧 Service Worker 등록 성공:', registration.scope);
            })
            .catch(error => {
                console.log('❌ Service Worker 등록 실패:', error);
            });
    });
}

/**
 * 전역 오류 처리 강화
 */
window.addEventListener('error', (e) => {
    console.error('🚨 전역 JavaScript 오류:', {
        message: e.message,
        filename: e.filename,
        lineno: e.lineno,
        colno: e.colno,
        error: e.error
    });
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('🚨 처리되지 않은 Promise 거부:', e.reason);
    e.preventDefault(); // 기본 오류 출력 방지
});

/**
 * 브라우저 지원 여부 확인
 */
function checkBrowserSupport() {
    const requiredFeatures = [
        'fetch',
        'Promise',
        'localStorage',
        'addEventListener',
        'querySelector'
    ];
    
    const unsupported = requiredFeatures.filter(feature => !(feature in window));
    
    if (unsupported.length > 0) {
        const message = `이 브라우저는 지원되지 않습니다. 다음 기능이 필요합니다: ${unsupported.join(', ')}`;
        document.body.innerHTML = `
            <div class="min-h-screen flex items-center justify-center bg-gray-50">
                <div class="max-w-md mx-auto text-center p-6">
                    <div class="text-6xl mb-4">🚫</div>
                    <h1 class="text-xl font-semibold text-gray-900 mb-2">브라우저 미지원</h1>
                    <p class="text-gray-600 mb-6">${message}</p>
                    <p class="text-sm text-gray-500">Chrome, Firefox, Safari, Edge 최신 버전을 사용해주세요.</p>
                </div>
            </div>
        `;
        return false;
    }
    
    return true;
}

// 브라우저 지원 확인
if (!checkBrowserSupport()) {
    console.error('❌ 브라우저 지원 검사 실패');
}

/**
 * 앱 정보 출력 (개발 모드)
 */
if (window.location.hostname === 'localhost') {
    console.log(`
    🤖 BigQuery AI Assistant
    ========================
    Version: 2.1.0-modular
    Environment: Development
    Module Support: ✅
    
    Debug Commands:
    - window.bqApp: 앱 인스턴스
    - window.bqDebug(): 디버그 정보
    - window.bqReset(): 세션 리셋
    - window.bqPerf(): 성능 메트릭
    `);
}