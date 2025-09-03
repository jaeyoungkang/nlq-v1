"""LLM 설정 관리자

LLM 서비스 설정을 중앙에서 관리하는 매니저입니다.
설정 파일 로드, 캐싱, 런타임 리로드를 지원합니다.
"""

from typing import Optional, Dict, Any
from core.config.models import LLMConfig, LLMTaskConfig, LLMModelConfig
from core.config.config_loader import ConfigLoader
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class LLMConfigManager:
    """LLM 설정 관리자
    
    설정 파일 기반 LLM 파라미터 관리:
    - 태스크별 최적화된 설정 제공
    - 런타임 설정 리로드 지원
    - 캐싱을 통한 성능 최적화
    """
    
    def __init__(self, config_loader: Optional[ConfigLoader] = None, environment: Optional[str] = None):
        """초기화
        
        Args:
            config_loader: 설정 로더 (없으면 기본 생성)
            environment: 환경 이름 (없으면 FLASK_ENV 사용)
        """
        self.config_loader = config_loader or ConfigLoader()
        self.environment = environment
        self._config: Optional[LLMConfig] = None
        self._raw_config: Optional[Dict[str, Any]] = None
        
        # 초기 설정 로드
        self.reload_config()
    
    def _parse_config(self, raw_config: Dict[str, Any]) -> LLMConfig:
        """원시 설정을 LLMConfig 객체로 파싱
        
        Args:
            raw_config: YAML에서 로드한 원시 설정
            
        Returns:
            파싱된 LLMConfig 객체
        """
        llm_section = raw_config.get("llm", {})
        
        # 태스크별 설정 파싱
        tasks_config = llm_section.get("tasks", {})
        
        # 각 태스크 설정 생성
        task_configs = {}
        for task_name in ["classification", "sql_generation", "data_analysis", 
                         "guide_generation", "out_of_scope"]:
            task_data = tasks_config.get(task_name, {})
            if task_data:
                task_configs[task_name] = LLMModelConfig(
                    model_id=task_data.get("model", llm_section.get("default_model")),
                    max_tokens=task_data.get("max_tokens", 500),
                    temperature=task_data.get("temperature", 0.5),
                    confidence=task_data.get("confidence")
                )
        
        # 누락된 태스크는 기본값으로 생성
        default_model = llm_section.get("default_model", "claude-3-5-haiku-20241022")
        for task_name in ["classification", "sql_generation", "data_analysis", 
                         "guide_generation", "out_of_scope"]:
            if task_name not in task_configs:
                # 태스크별 기본값
                defaults = {
                    "classification": {"max_tokens": 300, "temperature": 0.3},
                    "sql_generation": {"max_tokens": 1200, "temperature": 0.1},
                    "data_analysis": {"max_tokens": 1200, "temperature": 0.7},
                    "guide_generation": {"max_tokens": 800, "temperature": 0.7},
                    "out_of_scope": {"max_tokens": 400, "temperature": 0.5}
                }
                task_defaults = defaults.get(task_name, {"max_tokens": 500, "temperature": 0.5})
                task_configs[task_name] = LLMModelConfig(
                    model_id=default_model,
                    **task_defaults
                )
        
        # LLMTaskConfig 생성
        llm_tasks = LLMTaskConfig(
            classification=task_configs["classification"],
            sql_generation=task_configs["sql_generation"],
            data_analysis=task_configs["data_analysis"],
            guide_generation=task_configs["guide_generation"],
            out_of_scope=task_configs["out_of_scope"]
        )
        
        # LLMConfig 생성
        return LLMConfig(
            default_model=default_model,
            available_models=llm_section.get("available_models", [default_model]),
            tasks=llm_tasks
        )
    
    def reload_config(self) -> None:
        """설정 리로드
        
        설정 파일을 다시 읽어서 메모리에 로드합니다.
        런타임 중 설정 변경 시 사용합니다.
        """
        try:
            # 원시 설정 로드
            self._raw_config = self.config_loader.load_config(self.environment)
            
            # LLMConfig 객체로 파싱
            self._config = self._parse_config(self._raw_config)
            
            logger.info(f"LLM config reloaded. Default model: {self._config.default_model}")
            
            # 로드된 설정 요약 로깅
            for task_type in ["classification", "sql_generation", "data_analysis", 
                            "guide_generation", "out_of_scope"]:
                config = self._config.tasks.get_config(task_type)
                logger.debug(f"Task '{task_type}': model={config.model_id}, "
                           f"max_tokens={config.max_tokens}, temperature={config.temperature}")
                
        except Exception as e:
            logger.error(f"Failed to reload config: {str(e)}")
            # 설정 로드 실패 시 기본값 유지 또는 재시도 로직
            if self._config is None:
                # 최소한의 기본 설정 생성
                self._create_fallback_config()
    
    def _create_fallback_config(self) -> None:
        """폴백 설정 생성
        
        설정 파일 로드 실패 시 하드코딩된 기본값 사용
        """
        logger.warning("Using fallback config due to load failure")
        
        default_model = "claude-3-5-haiku-20241022"
        
        # 하드코딩된 기본값 (기존 코드와 동일)
        tasks = LLMTaskConfig(
            classification=LLMModelConfig(default_model, 300, 0.3, 0.5),
            sql_generation=LLMModelConfig(default_model, 1200, 0.1, 0.8),
            data_analysis=LLMModelConfig(default_model, 1200, 0.7),
            guide_generation=LLMModelConfig(default_model, 800, 0.7),
            out_of_scope=LLMModelConfig(default_model, 400, 0.5)
        )
        
        self._config = LLMConfig(
            default_model=default_model,
            available_models=[default_model],
            tasks=tasks
        )
    
    def get_config(self, task_type: str) -> LLMModelConfig:
        """태스크별 설정 조회
        
        Args:
            task_type: 태스크 유형 (classification, sql_generation 등)
            
        Returns:
            해당 태스크의 LLM 설정
            
        Raises:
            ValueError: 알 수 없는 태스크 유형
        """
        if self._config is None:
            self.reload_config()
        
        return self._config.tasks.get_config(task_type)
    
    def get_default_model(self) -> str:
        """기본 모델 ID 조회
        
        Returns:
            기본 LLM 모델 ID
        """
        if self._config is None:
            self.reload_config()
        
        return self._config.default_model
    
    def get_available_models(self) -> list[str]:
        """사용 가능한 모델 목록 조회
        
        Returns:
            사용 가능한 모델 ID 목록
        """
        if self._config is None:
            self.reload_config()
        
        return self._config.available_models
    
    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인
        
        Args:
            model_id: 확인할 모델 ID
            
        Returns:
            사용 가능 여부
        """
        return model_id in self.get_available_models()
    
    def get_raw_config(self) -> Dict[str, Any]:
        """원시 설정 딕셔너리 조회
        
        디버깅이나 설정 확인용
        
        Returns:
            원시 설정 딕셔너리
        """
        if self._raw_config is None:
            self.reload_config()
        
        return self._raw_config or {}