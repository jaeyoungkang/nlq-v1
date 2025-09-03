# Firebase 설정 파일들

이 디렉토리는 Firestore 관련 Firebase 설정 파일들을 포함합니다.

## 파일 목록

### `firebase.json`
- Firebase 프로젝트 설정 파일
- Firestore 규칙 및 인덱스 파일 경로 지정

### `firestore.rules`
- Firestore 보안 규칙 정의
- 사용자별 데이터 접근 제어  
- **이메일 기반 통합 보안 규칙**: `request.auth.token.email` 기반 접근 제어
- **whitelist 컬렉션**: 사용자는 자신의 이메일 문서만 읽기 가능
- **users 컬렉션**: 사용자는 자신의 이메일 문서와 conversations만 접근 가능

### `firestore.indexes.json`
- Firestore 복합 인덱스 설정
- 쿼리 성능 최적화를 위한 인덱스 정의

## 배포 명령어

### 보안 규칙 배포
```bash
cd backend/firebase
firebase deploy --only firestore:rules --project nlq-ex
```

### 인덱스 배포
```bash
cd backend/firebase
firebase deploy --only firestore:indexes --project nlq-ex
```

### 전체 Firestore 설정 배포
```bash
cd backend/firebase
firebase deploy --only firestore --project nlq-ex
```

## 주의사항

- 배포 전 반드시 규칙 파일 문법 검사 수행
- 프로덕션 배포 시 규칙 테스트 권장
- 인덱스 생성은 시간이 걸릴 수 있음 (대용량 데이터의 경우)

## 인덱스 구조 (이메일 기반 호환)

### `firestore.indexes.json` 구성
현재 구성된 복합 인덱스들은 **이메일 기반 아키텍처와 완전 호환**됩니다:

```json
{
  "collectionGroup": "conversations",
  "fields": [
    {"fieldPath": "user_id", "order": "ASCENDING"},     # 이메일 값 사용
    {"fieldPath": "timestamp", "order": "DESCENDING"}  # 최신순 정렬
  ]
}
```

### 인덱스 호환성 분석 ✅
- **필드 이름 동일**: `user_id` 필드명은 변경 없음
- **데이터 타입 호환**: Google user_id (문자열) → 이메일 (문자열)
- **쿼리 패턴 동일**: `user_id + timestamp` 조합 쿼리 계속 사용
- **성능 영향 없음**: 인덱스 구조 변경 불필요

### 지원하는 쿼리 패턴
```javascript
// 사용자별 최신 대화 조회 (이메일 기반)
users/{email}/conversations
  .where('user_id', '==', email)
  .orderBy('timestamp', 'desc')
  .limit(10)

// 타입별 대화 조회
users/{email}/conversations
  .where('user_id', '==', email)
  .where('block_type', '==', 'QUERY')
  .orderBy('timestamp', 'desc')

// 상태별 대화 조회  
users/{email}/conversations
  .where('user_id', '==', email)
  .where('status', '==', 'completed')
  .orderBy('timestamp', 'desc')
```

## 프로젝트 정보

- **프로젝트 ID**: nlq-ex
- **리전**: asia-northeast3
- **데이터베이스**: (default)