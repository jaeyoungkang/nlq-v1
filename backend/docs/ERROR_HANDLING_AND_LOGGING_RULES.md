# 에러 핸들링 및 로깅 룰 (Error Handling & Logging Rules)

> LLM 코드 생성 시 반드시 준수해야 할 에러 핸들링 및 로깅 표준

## 📋 목차

- [개요](#개요)
- [에러 핸들링 규칙](#에러-핸들링-규칙)
- [로깅 규칙](#로깅-규칙)
- [코드 예시](#코드-예시)
- [금지사항](#금지사항)

## 🎯 개요

이 문서는 NLDAA 백엔드 프로젝트에서 일관된 에러 핸들링과 로깅을 위한 표준 규칙을 정의합니다. 모든 새로운 코드는 이 규칙을 따라야 하며, LLM이 코드를 생성할 때도 이 규칙을 엄격히 준수해야 합니다.

## 🚨 에러 핸들링 규칙

### 1. 필수 Import

모든 파일에서 에러 처리가 필요한 경우 다음을 import해야 합니다:

```python
from utils.error_utils import ErrorResponse, SuccessResponse
```

### 2. 표준 에러 응답 생성

#### 기본 에러 응답
```python
# ❌ 금지: 직접 딕셔너리 생성
error_response = {
    "success": False,
    "error": "오류 메시지"
}

# ✅ 권장: ErrorResponse 클래스 사용
error_response = ErrorResponse.create("오류 메시지", "error_type")
```

#### 특수 에러 타입별 메서드 사용
```python
# 입력 검증 에러
ErrorResponse.validation_error("필수 필드가 누락되었습니다")

# 서비스 에러
ErrorResponse.service_error("BigQuery 연결 실패", "bigquery")

# 인증 에러
ErrorResponse.auth_error("토큰이 유효하지 않습니다")

# 권한 에러
ErrorResponse.permission_error("관리자 권한이 필요합니다")

# 리소스 없음 에러
ErrorResponse.not_found_error("요청하신 대화를 찾을 수 없습니다")

# 내부 서버 에러
ErrorResponse.internal_error("예상치 못한 오류가 발생했습니다")
```

### 3. 성공 응답 생성

```python
# 기본 성공 응답
SuccessResponse.create("요청이 성공적으로 처리되었습니다")

# 데이터 포함 성공 응답
SuccessResponse.create("조회 완료", data={"results": results})
```

### 4. Flask 라우트에서의 에러 처리 패턴

```python
@app.route('/api/example', methods=['POST'])
@require_auth
def example_endpoint():
    try:
        # 입력 검증
        if not request.json:
            return jsonify(ErrorResponse.validation_error("JSON 데이터가 필요합니다")), 400
        
        # 비즈니스 로직
        result = some_service.process_data(request.json)
        
        if not result['success']:
            return jsonify(ErrorResponse.service_error(
                result['error'], 
                "service_name"
            )), 500
        
        # 성공 응답
        return jsonify(SuccessResponse.create("처리 완료", data=result['data']))
        
    except ValueError as e:
        return jsonify(ErrorResponse.validation_error(str(e))), 400
    except Exception as e:
        return jsonify(ErrorResponse.internal_error(f"처리 실패: {str(e)}")), 500
```

### 5. 서비스 클래스에서의 에러 처리

```python
def some_service_method(self, data):
    """서비스 메서드 예시"""
    try:
        # 비즈니스 로직
        result = self.process(data)
        
        return {
            "success": True,
            "data": result
        }
        
    except SomeSpecificException as e:
        self.logger.error(f"특정 오류 발생: {str(e)}")
        return {
            "success": False,
            "error": f"처리 중 오류: {str(e)}",
            "error_type": "processing_error"
        }
    except Exception as e:
        self.logger.error(f"예상치 못한 오류: {str(e)}")
        return {
            "success": False,
            "error": f"예상치 못한 오류: {str(e)}",
            "error_type": "unexpected_error"
        }
```

## 📝 로깅 규칙

### 1. 필수 Import 및 초기화

```python
from utils.logging_utils import get_logger

# 클래스 내부에서
class SomeClass:
    def __init__(self):
        self.logger = get_logger(__name__)

# 함수/모듈 레벨에서
logger = get_logger(__name__)
```

### 2. 로깅 메서드 사용 규칙

#### 성공/완료 관련 로그
```python
logger.success("사용자 인증 성공")
logger.completed("쿼리 실행 완료")
logger.created("테이블 생성 완료")
logger.saved("대화 저장 완료")
```

#### 진행/처리 관련 로그
```python
logger.processing("데이터 처리 중")
logger.loading("설정 로딩 중")
logger.authenticating("사용자 인증 처리 중")
logger.querying("BigQuery 실행 중")
```

#### 경고 로그
```python
logger.warning("설정값이 기본값으로 설정됨")
logger.access_denied("접근 권한 없음")
logger.deprecated("이 메서드는 deprecated됩니다")
```

#### 에러 로그
```python
logger.error("일반적인 에러 발생")
logger.critical("치명적인 시스템 오류")
logger.auth_error("인증 관련 에러")
logger.db_error("데이터베이스 연결 오류")
```

#### 정보/디버그 로그
```python
logger.info("일반 정보")
logger.debug("디버그 정보")
logger.stats("통계 정보")
logger.config("설정 정보")
```

#### 특수 목적 로그
```python
logger.startup("애플리케이션 시작")
logger.shutdown("애플리케이션 종료")
logger.cleanup("정리 작업 수행")
logger.user_action("사용자 액션 수행")
```

### 3. 로깅 레벨 가이드라인

| 레벨 | 사용 시점 | 예시 |
|------|-----------|------|
| **DEBUG** | 개발 시 상세 정보 | `logger.debug("변수값 확인")` |
| **INFO** | 일반적인 정보, 성공 | `logger.success("처리 완료")` |
| **WARNING** | 주의가 필요한 상황 | `logger.warning("설정값 누락")` |
| **ERROR** | 처리 가능한 오류 | `logger.error("API 호출 실패")` |
| **CRITICAL** | 시스템 중단급 오류 | `logger.critical("서버 시작 실패")` |

### 4. 로그 메시지 작성 규칙

#### ✅ 좋은 로그 메시지
```python
logger.success("BigQuery client initialized successfully (Project: nlq-ex, Location: asia-northeast3)")
logger.error("사용자 인증 실패: 토큰 만료")
logger.processing("SQL 쿼리 실행 중: SELECT COUNT(*) FROM events")
logger.stats("화이트리스트 사용자: 총 25명 (active: 20명, pending: 5명)")
```

#### ❌ 피해야 할 로그 메시지
```python
logger.info("✅ Success")  # 이모지 중복
logger.error("❌ Error occurred")  # 이모지 중복
logger.info("Something happened")  # 너무 모호함
logger.debug("Debug")  # 의미 없는 메시지
```

## 💡 코드 예시

### 완전한 Flask 라우트 예시

```python
from flask import Blueprint, request, jsonify, g
from utils.auth_utils import require_auth
from utils.error_utils import ErrorResponse, SuccessResponse
from utils.logging_utils import get_logger

logger = get_logger(__name__)
example_bp = Blueprint('example', __name__, url_prefix='/api/example')

@example_bp.route('/process', methods=['POST'])
@require_auth
def process_data():
    """데이터 처리 엔드포인트"""
    try:
        logger.processing("데이터 처리 요청 시작")
        
        # 입력 검증
        if not request.json:
            logger.warning("JSON 데이터 누락")
            return jsonify(ErrorResponse.validation_error("JSON 데이터가 필요합니다")), 400
        
        data = request.json.get('data')
        if not data:
            logger.warning("필수 필드 'data' 누락")
            return jsonify(ErrorResponse.validation_error("'data' 필드가 필요합니다")), 400
        
        # 서비스 호출
        from services.data_service import DataService
        service = DataService()
        result = service.process(data)
        
        if not result['success']:
            logger.error(f"데이터 처리 실패: {result['error']}")
            return jsonify(ErrorResponse.service_error(
                result['error'], 
                "data_service"
            )), 500
        
        logger.success(f"데이터 처리 완료: {len(result['data'])}개 항목 처리됨")
        return jsonify(SuccessResponse.create(
            "데이터 처리가 완료되었습니다",
            data=result['data']
        ))
        
    except ValueError as e:
        logger.error(f"입력값 오류: {str(e)}")
        return jsonify(ErrorResponse.validation_error(f"입력값 오류: {str(e)}")), 400
    except Exception as e:
        logger.error(f"예상치 못한 오류: {str(e)}")
        return jsonify(ErrorResponse.internal_error(f"처리 실패: {str(e)}")), 500
```

### 서비스 클래스 예시

```python
from utils.logging_utils import get_logger
from typing import Dict, Any

class DataService:
    """데이터 처리 서비스"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데이터 처리 메서드"""
        try:
            self.logger.processing(f"데이터 처리 시작: {len(data)}개 항목")
            
            # 처리 로직
            processed_data = self._process_internal(data)
            
            self.logger.success(f"데이터 처리 완료: {len(processed_data)}개 결과 생성")
            return {
                "success": True,
                "data": processed_data
            }
            
        except ValueError as e:
            self.logger.error(f"데이터 검증 실패: {str(e)}")
            return {
                "success": False,
                "error": f"데이터 검증 실패: {str(e)}",
                "error_type": "validation_error"
            }
        except Exception as e:
            self.logger.error(f"데이터 처리 중 예상치 못한 오류: {str(e)}")
            return {
                "success": False,
                "error": f"처리 실패: {str(e)}",
                "error_type": "processing_error"
            }
    
    def _process_internal(self, data: Dict[str, Any]) -> list:
        """내부 처리 로직"""
        self.logger.debug("내부 처리 로직 실행")
        # 실제 처리 로직
        return []
```

## 🚫 금지사항

### 1. 직접 딕셔너리로 에러 응답 생성 금지

```python
# ❌ 절대 금지
return jsonify({
    "success": False,
    "error": "오류 메시지"
}), 400

# ✅ 반드시 이렇게
return jsonify(ErrorResponse.validation_error("오류 메시지")), 400
```

### 2. 이모지 직접 사용 금지

```python
# ❌ 절대 금지
logger.info("✅ 성공적으로 처리됨")
logger.error("❌ 오류 발생")

# ✅ 반드시 이렇게
logger.success("성공적으로 처리됨")
logger.error("오류 발생")
```

### 3. 표준 로거 대신 기본 logging 사용 금지

```python
# ❌ 절대 금지
import logging
logger = logging.getLogger(__name__)
logger.info("메시지")

# ✅ 반드시 이렇게
from utils.logging_utils import get_logger
logger = get_logger(__name__)
logger.info("메시지")
```

### 4. try-except 없는 에러 처리 금지

```python
# ❌ 절대 금지
@app.route('/api/endpoint')
def endpoint():
    result = risky_operation()  # 예외 발생 가능
    return jsonify(result)

# ✅ 반드시 이렇게
@app.route('/api/endpoint')
def endpoint():
    try:
        result = risky_operation()
        return jsonify(SuccessResponse.create("처리 완료", data=result))
    except Exception as e:
        return jsonify(ErrorResponse.internal_error(f"처리 실패: {str(e)}")), 500
```

### 5. 로그 메시지에 개인정보 포함 금지

```python
# ❌ 절대 금지
logger.info(f"사용자 로그인: {email}, 비밀번호: {password}")
logger.debug(f"API 키: {api_key}")

# ✅ 반드시 이렇게
logger.authenticating(f"사용자 로그인 시도: {email}")
logger.debug("API 키 검증 중")
```

## 📌 체크리스트

새로운 코드 작성 시 다음을 확인하세요:

- [ ] `utils.error_utils.ErrorResponse` 사용
- [ ] `utils.logging_utils.get_logger` 사용
- [ ] 적절한 HTTP 상태 코드 반환
- [ ] try-except 블록으로 예외 처리
- [ ] 로그 메시지에 이모지 직접 사용 안함
- [ ] 개인정보 로깅 안함
- [ ] 일관된 에러 응답 형식 사용
- [ ] 적절한 로그 레벨 사용

---

이 문서를 따라 코드를 작성하면 일관된 에러 처리와 로깅이 보장됩니다. 모든 LLM 코드 생성 시 이 규칙을 엄격히 준수해야 합니다.