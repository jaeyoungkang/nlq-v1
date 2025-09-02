#!/usr/bin/env python3
"""
Firestore 화이트리스트에 사용자 추가 스크립트
사용법: python3 add_user_to_whitelist.py <email> [status]
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

def add_user_to_whitelist(user_identifier: str, status: str = "active"):
    """사용자를 Firestore 화이트리스트에 추가"""
    try:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            print("❌ GOOGLE_CLOUD_PROJECT 환경변수가 설정되지 않았습니다")
            return False
        
        # Firestore 클라이언트 생성
        client = firestore.Client(project=project_id)
        
        # 입력이 이메일인지 user_id인지 판단
        is_email = "@" in user_identifier
        
        if is_email:
            # 이메일이 입력된 경우
            email = user_identifier
            # Google user_id는 사용자가 직접 입력해야 함
            user_id = input(f"Google user_id를 입력하세요 (이메일: {email}): ").strip()
            if not user_id:
                print("❌ Google user_id가 필요합니다")
                return False
        else:
            # user_id가 입력된 경우
            user_id = user_identifier
            email = input(f"이메일을 입력하세요 (user_id: {user_id}): ").strip()
            if not email or "@" not in email:
                print("❌ 유효한 이메일이 필요합니다")
                return False
        
        # 사용자 데이터 준비
        user_data = {
            'user_id': user_id,      # Google user_id를 실제 user_id로 사용
            'email': email,          # 이메일은 별도 필드
            'status': status,
            'created_at': datetime.now(timezone.utc),
            'last_login': None
        }
        
        # Firestore whitelist 컬렉션에 사용자 추가 (user_id를 문서 ID로 사용)
        whitelist_ref = client.collection("whitelist").document(user_id)
        whitelist_ref.set(user_data, merge=True)
        
        print(f"✅ 사용자가 화이트리스트에 추가되었습니다:")
        print(f"   - Google user_id: {user_id}")
        print(f"   - 이메일: {email}")
        print(f"   - 상태: {status}")
        print(f"   - 컬렉션: whitelist")
        print(f"   - 문서 ID: {user_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 사용자 추가 중 오류 발생: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("사용법: python3 add_user_to_whitelist.py <email_or_user_id> [status]")
        print("예시: python3 add_user_to_whitelist.py user@example.com active")
        print("예시: python3 add_user_to_whitelist.py 108731499195466851171 active")
        print("상태 옵션: active (기본값), pending, inactive")
        sys.exit(1)
    
    user_identifier = sys.argv[1]
    status = sys.argv[2] if len(sys.argv) > 2 else "active"
    
    if status not in ["active", "pending", "inactive"]:
        print("❌ 잘못된 상태값입니다. active, pending, inactive 중 선택하세요.")
        sys.exit(1)
    
    print(f"🔄 Firestore 화이트리스트에 사용자 추가 중...")
    success = add_user_to_whitelist(user_identifier, status)
    
    if success:
        print("🎉 완료!")
    else:
        print("💥 실패!")
        sys.exit(1)

if __name__ == "__main__":
    main()