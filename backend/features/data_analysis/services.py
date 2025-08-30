"""
Data Analysis Service - 데이터 분석 전담 서비스
"""

from typing import Dict, Any, List, Optional
from core.models import BlockType, ContextBlock, context_blocks_to_llm_format
from .models import AnalysisRequest, AnalysisResult
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """데이터 분석 전담 서비스 - LLM을 사용한 분석 응답 생성"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def process_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """
        데이터 분석 처리
        
        Args:
            request: 분석 요청 (ContextBlock 포함)
            
        Returns:
            AnalysisResult: 분석 결과
        """
        # ContextBlock 상태를 processing으로 변경
        request.context_block.status = "processing"
        request.context_block.block_type = BlockType.ANALYSIS
        
        try:
            logger.info(f"📊 데이터 분석 시작: {request.query[:50]}...")
            
            # 1. LLM을 통한 데이터 분석 (ContextBlock 직접 전달)
            analysis_result = self.llm_client.analyze_data(
                request.query,
                request.context_blocks
            )
            
            # 2. ContextBlock 업데이트
            if analysis_result.get("success"):
                analysis_content = analysis_result.get("analysis", "")
                request.context_block.assistant_response = analysis_content
                request.context_block.status = "completed"
                
                return AnalysisResult(
                    success=True,
                    analysis_content=analysis_content,
                    context_block=request.context_block
                )
            else:
                # 분석 실패
                request.context_block.status = "failed"
                error_msg = analysis_result.get("error", "분석 중 오류가 발생했습니다.")
                
                return AnalysisResult(
                    success=False,
                    analysis_content="분석을 수행할 수 없습니다.",
                    context_block=request.context_block,
                    error=error_msg
                )
                
        except Exception as e:
            logger.error(f"데이터 분석 중 오류: {str(e)}")
            request.context_block.status = "failed"
            
            return AnalysisResult(
                success=False,
                analysis_content="분석 중 오류가 발생했습니다.",
                context_block=request.context_block,
                error=str(e)
            )
    
    def _generate_no_data_response(self, request: AnalysisRequest) -> AnalysisResult:
        """
        이전 데이터가 없을 때의 응답 생성
        
        Args:
            request: 분석 요청
            
        Returns:
            AnalysisResult: 기본 응답
        """
        content = "분석할 데이터가 없습니다. 먼저 데이터를 조회한 후 분석을 요청해주세요."
        request.context_block.assistant_response = content
        request.context_block.status = "completed"
        
        return AnalysisResult(
            success=True,
            analysis_content=content,
            context_block=request.context_block
        )