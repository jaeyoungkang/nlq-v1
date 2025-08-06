"""
BigQuery 유틸리티 클래스 - 하위 호환성을 위한 래퍼
기존 코드와의 호환성을 유지하면서 새로운 모듈 구조로 리다이렉트
"""

import logging
from .bigquery import BigQueryClient

logger = logging.getLogger(__name__)

# 기존 코드와의 호환성을 위해 모든 exports를 그대로 유지
__all__ = ['BigQueryClient']

logger.info("✅ BigQuery 서비스 모듈 분할 완료 - 하위 호환성 유지됨")