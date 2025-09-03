#!/usr/bin/env python3
"""
Firestore 화이트리스트에 사용자 이메일 추가 스크립트 (단순화)
사용법: python3 add_user_to_whitelist.py <email>
"""

import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 환경 변수 로드
from dotenv import load_dotenv
env_path = project_root / '.env.local'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Environment variables loaded from {env_path}")
else:
    print(f"⚠️  Environment file not found: {env_path}")

# Firestore 클라이언트 초기화
from google.cloud import firestore

def add_user_to_whitelist(email: str):
    """이메일을 Firestore 화이트리스트에 추가 (단순화된 구조)"""
    try:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            print("❌ GOOGLE_CLOUD_PROJECT 환경변수가 설정되지 않았습니다")
            return False
        
        # 이메일 유효성 검사
        if not email or "@" not in email:
            print("❌ 유효한 이메일이 필요합니다")
            return False
        
        # Firestore 클라이언트 생성
        client = firestore.Client(project=project_id)
        
        # 이미 존재하는지 확인 (이메일을 문서 ID로 사용)
        whitelist_ref = client.collection("whitelist").document(email)
        existing_doc = whitelist_ref.get()
        
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            print(f"⚠️  이메일 {email}이 이미 화이트리스트에 등록되어 있습니다:")
            print(f"   - 생성일: {existing_data.get('created_at', '알 수 없음')}")
            
            # 사용자에게 덮어쓸지 확인
            response = input("이미 등록된 사용자입니다. 계속하시겠습니까? (y/N): ").strip().lower()
            if response != 'y':
                print("취소되었습니다.")
                return False
        
        # 단순화된 화이트리스트 데이터 구조
        whitelist_data = {
            'email': email,
            'created_at': datetime.now(timezone.utc)
        }
        
        # Firestore whitelist 컬렉션에 이메일 추가 (이메일을 문서 ID로 사용)
        whitelist_ref.set(whitelist_data, merge=True)
        
        print(f"✅ 사용자가 화이트리스트에 추가되었습니다:")
        print(f"   - 이메일: {email}")
        print(f"   - 컬렉션: whitelist")
        print(f"   - 문서 ID: {email}")
        print(f"   - 구조: 단순화 (이메일 + 생성일만 저장)")
        
        return True
        
    except Exception as e:
        print(f"❌ 사용자 추가 중 오류 발생: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("사용법: python3 add_user_to_whitelist.py <email>")
        print("예시: python3 add_user_to_whitelist.py user@example.com")
        print("설명: 이메일을 화이트리스트에 추가합니다 (존재하면 허용, 없으면 차단)")
        sys.exit(1)
    
    email = sys.argv[1]
    
    # 이메일 유효성 검사
    if "@" not in email:
        print("❌ 유효한 이메일 주소를 입력해주세요.")
        sys.exit(1)
    
    print(f"🔄 Firestore 화이트리스트에 이메일 추가 중...")
    print(f"   - 이메일: {email}")
    print(f"   - 방식: 이메일을 문서 ID로 사용")
    
    success = add_user_to_whitelist(email)
    
    if success:
        print("🎉 완료!")
    else:
        print("💥 실패!")
        sys.exit(1)

if __name__ == "__main__":
    main()