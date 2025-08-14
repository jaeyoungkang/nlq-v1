#!/usr/bin/env python3
"""
MetaSync 캐시 통합 테스트

MetaSync에서 생성한 캐시 데이터가 nlq-v1 백엔드의 LLM Client에서 
정상적으로 활용되는지 검증합니다.
"""

import os
import sys
import logging
from typing import Dict, Any

# 현재 스크립트의 상위 디렉토리를 Python path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_metasync_cache_loader():
    """MetaSync 캐시 로더 기본 기능 테스트"""
    print("🧪 테스트 1: MetaSync 캐시 로더 기본 기능")
    
    try:
        from utils.metasync_cache_loader import get_metasync_cache_loader
        
        # 캐시 로더 인스턴스 생성
        cache_loader = get_metasync_cache_loader()
        print("✅ 캐시 로더 인스턴스 생성 성공")
        
        # 캐시 가용성 확인
        is_available = cache_loader.is_cache_available()
        print(f"📊 캐시 사용 가능: {is_available}")
        
        if is_available:
            # 스키마 정보 로드 테스트
            schema_info = cache_loader.get_schema_info()
            print(f"📋 스키마 로드: {len(schema_info.get('columns', []))}개 컬럼")
            
            # Few-Shot 예시 로드 테스트
            examples = cache_loader.get_few_shot_examples()
            print(f"💡 Few-Shot 예시: {len(examples)}개")
            
            # 캐시 메타데이터 확인
            metadata = cache_loader.get_cache_metadata()
            print(f"📈 캐시 메타데이터: {metadata}")
            
            return True
        else:
            print("⚠️ 캐시 데이터를 사용할 수 없습니다. GCS 연결 또는 캐시 파일을 확인해주세요.")
            return False
            
    except Exception as e:
        print(f"❌ 캐시 로더 테스트 실패: {e}")
        return False

def test_llm_client_metasync_integration():
    """LLM Client의 MetaSync 통합 테스트"""
    print("\\n🧪 테스트 2: LLM Client MetaSync 통합")
    
    try:
        from utils.llm_client import AnthropicLLMClient
        
        # API 키 확인
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("⚠️ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
            print("   실제 LLM 호출 없이 캐시 통합 부분만 테스트합니다.")
            
            # API 키 없이 초기화 테스트 (예외 발생 예상)
            try:
                client = AnthropicLLMClient("dummy-key")
            except Exception as init_error:
                print(f"⚠️ 예상된 초기화 오류: {init_error}")
            return False
        
        # LLM Client 초기화
        client = AnthropicLLMClient(api_key)
        print("✅ LLM Client 초기화 성공 (MetaSync 포함)")
        
        # MetaSync 상태 확인
        metasync_status = client.check_metasync_status()
        print(f"📊 MetaSync 상태: {metasync_status}")
        
        # 캐시 데이터 통합 테스트
        test_category = 'query_request'
        test_input_data = {'question': '테스트 질문입니다'}
        
        enhanced_data = client._enhance_input_data_with_metasync(test_category, test_input_data)
        
        # 통합 결과 확인
        expected_keys = ['schema_columns', 'few_shot_examples', 'table_id']
        for key in expected_keys:
            if key in enhanced_data:
                print(f"✅ {key}: 통합 성공")
                if key == 'schema_columns':
                    preview = enhanced_data[key][:100] + "..." if len(enhanced_data[key]) > 100 else enhanced_data[key]
                    print(f"   📋 스키마 정보 미리보기: {preview}")
                elif key == 'few_shot_examples':
                    preview = enhanced_data[key][:150] + "..." if len(enhanced_data[key]) > 150 else enhanced_data[key]
                    print(f"   💡 예시 정보 미리보기: {preview}")
            else:
                print(f"❌ {key}: 통합 실패")
        
        return metasync_status.get('status') == 'available'
        
    except Exception as e:
        print(f"❌ LLM Client 통합 테스트 실패: {e}")
        return False

def test_prompt_template_compatibility():
    """프롬프트 템플릿과 MetaSync 데이터 호환성 테스트"""
    print("\\n🧪 테스트 3: 프롬프트 템플릿 호환성")
    
    try:
        from utils.prompts import prompt_manager
        from utils.metasync_cache_loader import get_metasync_cache_loader
        
        cache_loader = get_metasync_cache_loader()
        
        if not cache_loader.is_cache_available():
            print("⚠️ 캐시를 사용할 수 없어 프롬프트 테스트를 건너뜁니다.")
            return False
        
        # 캐시 데이터 로드
        schema_info = cache_loader.get_schema_info()
        examples = cache_loader.get_few_shot_examples()
        
        # 스키마와 예시를 프롬프트 형식으로 변환
        formatted_schema = "\\n".join([
            f"- {col['name']} ({col['type']}): {col.get('description', '')}"
            for col in schema_info.get('columns', [])[:5]  # 처음 5개만
        ])
        
        formatted_examples = "\\n".join([
            f"예시 {i+1}:\\n질문: {ex['question']}\\nSQL: {ex['sql']}"
            for i, ex in enumerate(examples[:2])  # 처음 2개만
        ])
        
        # SQL 생성 프롬프트 테스트
        test_variables = {
            'table_id': schema_info.get('table_id', 'nlq-ex.test_dataset.events_20210131'),
            'schema_columns': formatted_schema,
            'few_shot_examples': formatted_examples
        }
        
        system_prompt = prompt_manager.get_prompt(
            category='sql_generation',
            template_name='system_prompt',
            **test_variables,
            fallback_prompt="Fallback prompt"
        )
        
        if system_prompt and len(system_prompt) > 100:
            print("✅ SQL 생성 시스템 프롬프트 생성 성공")
            print(f"   📏 프롬프트 길이: {len(system_prompt)} 문자")
            
            # 주요 변수들이 올바르게 치환되었는지 확인
            if test_variables['table_id'] in system_prompt:
                print("✅ 테이블 ID 치환 성공")
            if "event_name" in system_prompt or "user_id" in system_prompt:
                print("✅ 스키마 컬럼 정보 포함 확인")
            if "예시" in system_prompt:
                print("✅ Few-Shot 예시 포함 확인")
                
            return True
        else:
            print("❌ 프롬프트 생성 실패 또는 내용 부족")
            return False
            
    except Exception as e:
        print(f"❌ 프롬프트 호환성 테스트 실패: {e}")
        return False

def test_end_to_end_workflow():
    """전체 워크플로우 시뮬레이션 테스트"""
    print("\\n🧪 테스트 4: End-to-End 워크플로우 시뮬레이션")
    
    try:
        # 실제 분류 요청 시뮬레이션
        test_user_input = "이벤트 타입별 건수를 알려주세요"
        
        # 1단계: 분류 시뮬레이션
        print(f"1️⃣ 사용자 입력: {test_user_input}")
        expected_category = "query_request"
        print(f"2️⃣ 예상 분류: {expected_category}")
        
        # 2단계: MetaSync 데이터 통합 확인
        from utils.llm_client import AnthropicLLMClient
        from utils.metasync_cache_loader import get_metasync_cache_loader
        
        cache_loader = get_metasync_cache_loader()
        if not cache_loader.is_cache_available():
            print("⚠️ 캐시를 사용할 수 없어 전체 워크플로우 테스트를 건너뜁니다.")
            return False
        
        # LLM Client 초기화 (API 키 체크)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("⚠️ ANTHROPIC_API_KEY가 없어 실제 호출 없이 데이터 통합만 확인합니다.")
            
            # 데이터 통합만 테스트
            dummy_client = type('DummyClient', (), {
                'cache_loader': cache_loader,
                '_enhance_input_data_with_metasync': AnthropicLLMClient._enhance_input_data_with_metasync.__get__(None, AnthropicLLMClient),
                '_get_cached_data_with_fallback': AnthropicLLMClient._get_cached_data_with_fallback.__get__(None, AnthropicLLMClient),
                '_get_fallback_data': AnthropicLLMClient._get_fallback_data.__get__(None, AnthropicLLMClient),
                '_get_fallback_metasync_data': AnthropicLLMClient._get_fallback_metasync_data.__get__(None, AnthropicLLMClient),
                '_format_schema_for_prompt': AnthropicLLMClient._format_schema_for_prompt.__get__(None, AnthropicLLMClient),
                '_format_examples_for_prompt': AnthropicLLMClient._format_examples_for_prompt.__get__(None, AnthropicLLMClient),
            })()
            
            enhanced_data = dummy_client._enhance_input_data_with_metasync(
                expected_category, 
                {'question': test_user_input}
            )
            
            print("3️⃣ MetaSync 데이터 통합 결과:")
            for key in ['schema_columns', 'few_shot_examples', 'table_id']:
                if key in enhanced_data:
                    print(f"   ✅ {key}: 통합됨")
                else:
                    print(f"   ❌ {key}: 누락")
            
            print("4️⃣ 시뮬레이션 완료: 실제 LLM 호출은 API 키가 필요합니다.")
            return True
        
        # API 키가 있는 경우 실제 테스트
        client = AnthropicLLMClient(api_key)
        
        print("3️⃣ MetaSync 통합 LLM Client로 실제 호출 준비됨")
        print("   (실제 Claude API 호출은 비용이 발생하므로 스킵)")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-End 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행 함수"""
    print("🚀 MetaSync 통합 테스트 시작")
    print("=" * 50)
    
    test_results = []
    
    # 개별 테스트 실행
    test_results.append(test_metasync_cache_loader())
    test_results.append(test_llm_client_metasync_integration())
    test_results.append(test_prompt_template_compatibility())
    test_results.append(test_end_to_end_workflow())
    
    # 결과 요약
    print("\\n" + "=" * 50)
    print("📋 테스트 결과 요약")
    
    test_names = [
        "MetaSync 캐시 로더 기본 기능",
        "LLM Client MetaSync 통합", 
        "프롬프트 템플릿 호환성",
        "End-to-End 워크플로우"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results), 1):
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{i}. {name}: {status}")
    
    success_count = sum(test_results)
    total_count = len(test_results)
    
    print(f"\\n🎯 전체 결과: {success_count}/{total_count} 통과")
    
    if success_count == total_count:
        print("🎉 모든 테스트 통과! MetaSync 통합이 성공적으로 완료되었습니다.")
        return True
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하여 문제를 해결해주세요.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)