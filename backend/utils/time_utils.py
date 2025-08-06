# utils/time_utils.py
"""
시간 처리 표준화 유틸리티
모든 시간 관련 처리를 UTC로 통일하여 시간 동기화 문제 해결
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

class TimeManager:
    """시간 처리를 표준화하는 매니저 클래스"""
    
    @staticmethod
    def utc_now() -> datetime:
        """현재 UTC 시간 반환"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def utc_date_string() -> str:
        """현재 UTC 날짜를 YYYY-MM-DD 형식으로 반환"""
        return TimeManager.utc_now().strftime('%Y-%m-%d')
    
    @staticmethod
    def utc_datetime_string() -> str:
        """현재 UTC 시간을 ISO 형식으로 반환"""
        return TimeManager.utc_now().isoformat()
    
    @staticmethod
    def safe_utc_time(offset_seconds: int = -10) -> datetime:
        """
        안전한 UTC 시간 반환 (시간 동기화 문제 방지)
        
        Args:
            offset_seconds: 현재 시간에서 뺄 초 (기본값: -10초)
        
        Returns:
            offset이 적용된 UTC 시간
        """
        return TimeManager.utc_now() + timedelta(seconds=offset_seconds)
    
    @staticmethod
    def parse_utc_datetime(datetime_str: str) -> Optional[datetime]:
        """
        ISO 형식 문자열을 UTC datetime으로 파싱
        
        Args:
            datetime_str: ISO 형식 날짜시간 문자열
            
        Returns:
            파싱된 UTC datetime 또는 None
        """
        try:
            # ISO 형식 파싱 시도
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            
            # timezone이 없으면 UTC로 가정
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            # UTC로 변환
            return dt.astimezone(timezone.utc)
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def is_same_utc_date(dt1: datetime, dt2: datetime) -> bool:
        """
        두 datetime이 같은 UTC 날짜인지 확인
        
        Args:
            dt1: 첫 번째 datetime
            dt2: 두 번째 datetime
            
        Returns:
            같은 UTC 날짜인지 여부
        """
        utc_dt1 = dt1.astimezone(timezone.utc) if dt1.tzinfo else dt1.replace(tzinfo=timezone.utc)
        utc_dt2 = dt2.astimezone(timezone.utc) if dt2.tzinfo else dt2.replace(tzinfo=timezone.utc)
        
        return utc_dt1.date() == utc_dt2.date()
    
    @staticmethod
    def get_utc_date_range(days_ago: int = 0) -> tuple[datetime, datetime]:
        """
        UTC 날짜 범위 반환 (해당 날짜의 00:00:00 ~ 23:59:59)
        
        Args:
            days_ago: 며칠 전 (0 = 오늘)
            
        Returns:
            (start_datetime, end_datetime) UTC 기준
        """
        target_date = TimeManager.utc_now().date() - timedelta(days=days_ago)
        
        start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        return start_dt, end_dt