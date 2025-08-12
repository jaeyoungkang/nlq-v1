# 최적화된 Dockerfile for BigQuery AI Assistant Backend
FROM python:3.11-slim

# 메타데이터
LABEL maintainer="BigQuery AI Assistant"
LABEL version="1.0"
LABEL description="BigQuery AI Assistant Backend - Flask API Server"

# 환경변수 설정
ENV PYTHONPATH=/app \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 작업 디렉토리 설정
WORKDIR /app

# 비권한 사용자 생성
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# 시스템 패키지 설치 (한 번에 모든 필요한 패키지)
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    curl \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Python 의존성 먼저 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 애플리케이션 파일 소유권 변경
RUN chown -R appuser:appgroup /app

# 비권한 사용자로 전환
USER appuser

# 포트 설정
EXPOSE 8080

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Gunicorn으로 애플리케이션 실행
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300 "app:app"