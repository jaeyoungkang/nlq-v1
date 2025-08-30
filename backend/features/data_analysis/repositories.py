"""
Data Analysis Repository
데이터 분석 결과 저장 및 조회를 담당하는 리포지토리
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from core.repositories.base import BaseRepository, bigquery
from utils.logging_utils import get_logger
from .models import AnalysisRequest, AnalysisResult

logger = get_logger(__name__)


class DataAnalysisRepository(BaseRepository):
    """데이터 분석 결과를 저장하고 조회하는 리포지토리"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "asia-northeast3"):
        """
        DataAnalysisRepository 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: BigQuery 리전
        """
        super().__init__(
            table_name="analysis_results",
            dataset_name="v1",
            project_id=project_id,
            location=location
        )
    
    def ensure_table_exists(self) -> Dict[str, Any]:
        """analysis_results 테이블 존재 확인 및 생성 (ContextBlock 호환)"""
        try:
            dataset_ref = self.client.dataset(self.dataset_name)
            
            # 데이터셋 확인/생성
            try:
                self.client.get_dataset(dataset_ref)
            except bigquery.NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "NLQ-v1 analysis results dataset"
                self.client.create_dataset(dataset)
                logger.info(f"데이터셋 생성: {self.dataset_name}")
            
            # 테이블 확인/생성
            table_ref = dataset_ref.table(self.table_name)
            try:
                self.client.get_table(table_ref)
                return {"success": True, "action": "exists", "table_id": self.table_id}
            except bigquery.NotFound:
                # ContextBlock과 호환되는 분석 결과 스키마로 테이블 생성
                schema = [
                    # ContextBlock 기본 필드
                    bigquery.SchemaField("block_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"), 
                    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("block_type", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("user_request", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("assistant_response", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("execution_result", "JSON", mode="NULLABLE"),
                    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                    
                    # AnalysisResult 확장 필드
                    bigquery.SchemaField("analysis_id", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("analysis_content", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("success", "BOOLEAN", mode="NULLABLE"),
                    bigquery.SchemaField("error", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("analysis_type", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("metadata", "JSON", mode="NULLABLE")
                ]
                
                table = bigquery.Table(table_ref, schema=schema)
                table.description = "Data analysis results with ContextBlock compatibility"
                self.client.create_table(table)
                
                logger.info(f"analysis_results 테이블 생성 완료: {self.table_id}")
                return {"success": True, "action": "created", "table_id": self.table_id}
                
        except Exception as e:
            logger.error(f"analysis_results 테이블 확인/생성 중 오류: {str(e)}")
            return {"success": False, "error": str(e)}