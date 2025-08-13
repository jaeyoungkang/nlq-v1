#!/usr/bin/env python3
"""
컨텍스트 기능 기본 테스트 스크립트
Phase 1 구현 검증용
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

# 프로젝트 루트 디렉토리 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.bigquery.conversation_service import ConversationService
from utils.llm_client import AnthropicLLMClient

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_conversation_context():
    """대화 컨텍스트 조회 테스트"""
    logger.info("🧪 대화 컨텍스트 조회 테스트 시작")
    
    # 환경 변수 확인
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        logger.error("❌ GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다")
        return False
    
    try:
        # ConversationService 초기화
        conv_service = ConversationService(project_id)
        
        # 테스트용 대화 컨텍스트 생성
        test_conversation_id = "test_conv_context_001"
        test_user_id = "test_user_001"
        
        # 컨텍스트 조회 테스트 (빈 결과 예상)
        context_result = conv_service.get_conversation_context(
            conversation_id=test_conversation_id,
            user_id=test_user_id,
            max_messages=5
        )
        
        logger.info(f"✅ 컨텍스트 조회 결과: {context_result['success']}")
        logger.info(f"📊 조회된 메시지 수: {context_result.get('context_length', 0)}")
        
        return context_result['success']
        
    except Exception as e:
        logger.error(f"❌ 컨텍스트 조회 테스트 실패: {str(e)}")
        return False

def test_context_optimization():
    """컨텍스트 최적화 테스트"""
    logger.info("🧪 컨텍스트 최적화 테스트 시작")
    
    try:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'test-project')
        conv_service = ConversationService(project_id)
        
        # 테스트용 긴 메시지들 생성
        test_messages = [
            {
                "role": "user",
                "content": "안녕하세요. BigQuery에서 사용자 데이터를 조회하고 싶습니다. 지난 한 달간의 활성 사용자 수를 확인할 수 있을까요?",
                "timestamp": "2025-01-01T10:00:00Z",
                "metadata": {"query_type": "query_request"}
            },
            {
                "role": "assistant", 
                "content": "안녕하세요! 지난 한 달간의 활성 사용자 수를 조회하는 SQL을 생성해드리겠습니다. 다음과 같은 쿼리를 사용하시면 됩니다: SELECT COUNT(DISTINCT user_id) as active_users FROM events WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
                "timestamp": "2025-01-01T10:00:30Z", 
                "metadata": {"query_type": "query_request", "generated_sql": "SELECT COUNT(DISTINCT user_id) as active_users FROM events WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)"}
            },
            {
                "role": "user",
                "content": "그 중에서 프리미엄 사용자만 필터링할 수 있나요?",
                "timestamp": "2025-01-01T10:01:00Z",
                "metadata": {"query_type": "follow_up_query"}
            }
        ]
        
        # 최적화 전 크기
        original_size = len(test_messages)
        
        # 최적화 테스트 (작은 토큰 제한)
        optimized_messages = conv_service.optimize_context_size(test_messages, max_tokens=100)
        optimized_size = len(optimized_messages)
        
        logger.info(f"✅ 컨텍스트 최적화 완료: {original_size} → {optimized_size}개 메시지")
        
        # 최적화 결과 검증
        assert optimized_size <= original_size, "최적화 후 메시지 수가 증가했습니다"
        assert optimized_size > 0, "최적화 후 메시지가 모두 제거되었습니다"
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 컨텍스트 최적화 테스트 실패: {str(e)}")
        return False

def test_context_classification():
    """컨텍스트 기반 분류 테스트"""
    logger.info("🧪 컨텍스트 기반 분류 테스트 시작")
    
    # API 키 확인
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning("⚠️ ANTHROPIC_API_KEY가 설정되지 않아 분류 테스트를 건너뜁니다")
        return True
    
    try:
        # LLM 클라이언트 초기화
        llm_client = AnthropicLLMClient(api_key)
        
        # 테스트 시나리오 1: 컨텍스트 없는 기본 분류
        basic_input = "사용자 데이터 보여줘"
        basic_result = llm_client.classify_input_with_context(basic_input)
        
        logger.info(f"✅ 기본 분류 결과: {basic_result['classification']['category']}")
        
        # 테스트 시나리오 2: 컨텍스트 있는 분류
        context_messages = [
            {
                "role": "user",
                "content": "사용자 데이터 조회해줘",
                "timestamp": "2025-01-01T10:00:00Z",
                "metadata": {"query_type": "query_request"}
            },
            {
                "role": "assistant",
                "content": "사용자 데이터를 조회하는 SQL을 생성했습니다.",
                "timestamp": "2025-01-01T10:00:30Z",
                "metadata": {"query_type": "query_request", "generated_sql": "SELECT * FROM users"}
            }
        ]
        
        context_input = "그 중에서 활성 사용자만"
        context_result = llm_client.classify_input_with_context(context_input, context_messages)
        
        logger.info(f"✅ 컨텍스트 분류 결과: {context_result['classification']['category']}")
        
        # 결과 검증
        assert basic_result['success'], "기본 분류가 실패했습니다"
        assert context_result['success'], "컨텍스트 분류가 실패했습니다"
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 컨텍스트 분류 테스트 실패: {str(e)}")
        return False

def main():
    """전체 테스트 실행"""
    logger.info("🚀 Phase 1 컨텍스트 기능 테스트 시작")
    
    tests = [
        ("대화 컨텍스트 조회", test_conversation_context),
        ("컨텍스트 최적화", test_context_optimization), 
        ("컨텍스트 기반 분류", test_context_classification)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 {test_name} 테스트 실행 중...")
        result = test_func()
        results.append((test_name, result))
        
        if result:
            logger.info(f"✅ {test_name} 테스트 성공")
        else:
            logger.error(f"❌ {test_name} 테스트 실패")
    
    # 전체 결과 요약
    logger.info("\n📊 테스트 결과 요약:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"  - {test_name}: {status}")
    
    logger.info(f"\n🏁 전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        logger.info("🎉 Phase 1 컨텍스트 기능 구현 완료!")
        return True
    else:
        logger.error("💥 일부 테스트가 실패했습니다. 구현을 확인해주세요.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)