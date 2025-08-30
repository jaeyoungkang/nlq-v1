"""
Base repository for data access layer
Provides common database operations for all repositories
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# BigQuery 클래스들을 하위 리포지토리에서 사용할 수 있도록 export
__all__ = ['BaseRepository', 'bigquery', 'NotFound']

class BaseRepository:
    """
    기본 리포지토리 클래스
    모든 기능별 리포지토리가 상속받아 사용
    """
    
    def __init__(self, 
                 table_name: str,
                 dataset_name: Optional[str] = None,
                 project_id: Optional[str] = None,
                 location: str = "asia-northeast3"):
        """
        BaseRepository 초기화
        
        Args:
            table_name: BigQuery 테이블명
            dataset_name: BigQuery 데이터셋명 (기본값: 환경변수)
            project_id: Google Cloud 프로젝트 ID (기본값: 환경변수)
            location: BigQuery 리전
        """
        self.table_name = table_name
        self.dataset_name = dataset_name or os.getenv('BIGQUERY_DATASET', 'v1')
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.location = location
        
        if not self.project_id:
            raise ValueError("Google Cloud 프로젝트 ID가 설정되지 않았습니다")
        
        try:
            self.client = bigquery.Client(
                project=self.project_id, 
                location=self.location
            )
            self.table_id = f"{self.project_id}.{self.dataset_name}.{self.table_name}"
            logger.info(f"BaseRepository 초기화 완료: {self.table_id}")
        except Exception as e:
            logger.error(f"BaseRepository 초기화 실패: {str(e)}")
            raise
    
    
    def ensure_table_exists(self) -> Dict[str, Any]:
        """데이터셋과 테이블 존재 확인 및 필요시 생성"""
        try:
            dataset_ref = self.client.dataset(self.dataset_name)
            
            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
                logger.debug(f"데이터셋 확인: {self.dataset_name}")
            except NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = f"Dataset for {self.table_name}"
                self.client.create_dataset(dataset)
                logger.info(f"데이터셋 생성: {self.dataset_name}")
            
            # 테이블 확인
            table_ref = dataset_ref.table(self.table_name)
            try:
                self.client.get_table(table_ref)
                logger.debug(f"테이블 확인: {self.table_id}")
                return {"success": True, "action": "exists", "table_id": self.table_id}
            except NotFound:
                logger.warning(f"테이블이 존재하지 않습니다: {self.table_id}")
                return {"success": False, "error": f"테이블이 존재하지 않습니다: {self.table_id}"}
                
        except Exception as e:
            logger.error(f"테이블 확인/생성 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def save(self, data) -> Dict[str, Any]:
        """
        데이터를 BigQuery에 저장
        
        Args:
            data: 저장할 데이터 (Pydantic 모델, 딕셔너리, 또는 기타)
            
        Returns:
            저장 결과 딕셔너리
        """
        try:
            # 테이블 존재 확인
            ensure_result = self.ensure_table_exists()
            if not ensure_result.get('success'):
                return ensure_result
            
            # Pydantic 모델을 딕셔너리로 변환
            if isinstance(data, BaseModel):
                row_data = data.model_dump(mode='json', exclude_none=True)
            else:
                row_data = data if isinstance(data, dict) else {"data": data}
            
            # 날짜/시간 객체 처리
            row_data = self._serialize_datetime_fields(row_data)
            
            # BigQuery에 삽입
            table = self.client.get_table(self.table_id)
            errors = self.client.insert_rows_json(table, [row_data])
            
            if errors:
                logger.error(f"데이터 저장 실패: {errors}")
                return {"success": False, "error": f"저장 중 오류: {errors[0]}"}
            
            logger.info(f"데이터 저장 성공: {self.table_id}")
            return {"success": True, "message": "데이터가 성공적으로 저장되었습니다"}
            
        except Exception as e:
            logger.error(f"데이터 저장 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _serialize_datetime_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """날짜/시간 필드를 직렬화"""
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif hasattr(value, 'isoformat'):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = self._serialize_datetime_fields(value)
            elif isinstance(value, list):
                data[key] = [
                    self._serialize_datetime_fields(item) if isinstance(item, dict) 
                    else item.isoformat() if hasattr(item, 'isoformat')
                    else item
                    for item in value
                ]
        return data