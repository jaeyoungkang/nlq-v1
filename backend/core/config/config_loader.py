"""설정 파일 로더

YAML 설정 파일을 로드하고 환경 변수 오버라이드를 처리합니다.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from utils.logging_utils import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """설정 파일 로더
    
    YAML 파일 기반 계층적 설정 로드:
    1. default.yaml (기본값)
    2. {environment}.yaml (환경별 오버라이드)
    3. 환경 변수 (최우선)
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """초기화
        
        Args:
            config_dir: 설정 파일 디렉토리 경로
        """
        if config_dir is None:
            # 기본값: backend/config/
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)
        
        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {self.config_dir}")
        
        logger.info(f"ConfigLoader initialized with directory: {self.config_dir}")
    
    def load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """YAML 파일 로드
        
        Args:
            filename: 파일명 (예: default.yaml)
            
        Returns:
            파싱된 YAML 내용
        """
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}")
            return {}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"Loaded config from {filename}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config file {filename}: {str(e)}")
            return {}
    
    def deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """딕셔너리 깊은 병합
        
        override의 값이 base의 값을 덮어씁니다.
        중첩된 딕셔너리는 재귀적으로 병합됩니다.
        
        Args:
            base: 기본 딕셔너리
            override: 덮어쓸 딕셔너리
            
        Returns:
            병합된 딕셔너리
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 중첩된 딕셔너리는 재귀적으로 병합
                result[key] = self.deep_merge(result[key], value)
            else:
                # 단순 값은 덮어쓰기
                result[key] = value
        
        return result
    
    def apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """환경 변수 오버라이드 적용
        
        환경 변수 패턴:
        - LLM_DEFAULT_MODEL → llm.default_model
        - LLM_CLASSIFICATION_MAX_TOKENS → llm.tasks.classification.max_tokens
        - LLM_CLASSIFICATION_TEMPERATURE → llm.tasks.classification.temperature
        
        Args:
            config: 기본 설정
            
        Returns:
            환경 변수가 적용된 설정
        """
        env_mappings = {
            # 기본 모델
            "LLM_DEFAULT_MODEL": ["llm", "default_model"],
            
            # Classification 태스크
            "LLM_CLASSIFICATION_MODEL": ["llm", "tasks", "classification", "model"],
            "LLM_CLASSIFICATION_MAX_TOKENS": ["llm", "tasks", "classification", "max_tokens"],
            "LLM_CLASSIFICATION_TEMPERATURE": ["llm", "tasks", "classification", "temperature"],
            "LLM_CLASSIFICATION_CONFIDENCE": ["llm", "tasks", "classification", "confidence"],
            
            # SQL Generation 태스크
            "LLM_SQL_GENERATION_MODEL": ["llm", "tasks", "sql_generation", "model"],
            "LLM_SQL_GENERATION_MAX_TOKENS": ["llm", "tasks", "sql_generation", "max_tokens"],
            "LLM_SQL_GENERATION_TEMPERATURE": ["llm", "tasks", "sql_generation", "temperature"],
            "LLM_SQL_GENERATION_CONFIDENCE": ["llm", "tasks", "sql_generation", "confidence"],
            
            # Data Analysis 태스크
            "LLM_DATA_ANALYSIS_MODEL": ["llm", "tasks", "data_analysis", "model"],
            "LLM_DATA_ANALYSIS_MAX_TOKENS": ["llm", "tasks", "data_analysis", "max_tokens"],
            "LLM_DATA_ANALYSIS_TEMPERATURE": ["llm", "tasks", "data_analysis", "temperature"],
            
            # Guide Generation 태스크
            "LLM_GUIDE_GENERATION_MODEL": ["llm", "tasks", "guide_generation", "model"],
            "LLM_GUIDE_GENERATION_MAX_TOKENS": ["llm", "tasks", "guide_generation", "max_tokens"],
            "LLM_GUIDE_GENERATION_TEMPERATURE": ["llm", "tasks", "guide_generation", "temperature"],
            
            # Out of Scope 태스크
            "LLM_OUT_OF_SCOPE_MODEL": ["llm", "tasks", "out_of_scope", "model"],
            "LLM_OUT_OF_SCOPE_MAX_TOKENS": ["llm", "tasks", "out_of_scope", "max_tokens"],
            "LLM_OUT_OF_SCOPE_TEMPERATURE": ["llm", "tasks", "out_of_scope", "temperature"],
        }
        
        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # 중첩된 경로에 값 설정
                current = config
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # 타입 변환
                last_key = path[-1]
                if "max_tokens" in last_key:
                    current[last_key] = int(value)
                elif "temperature" in last_key or "confidence" in last_key:
                    current[last_key] = float(value)
                else:
                    current[last_key] = value
                
                logger.info(f"Applied env override: {env_var} = {value}")
        
        return config
    
    def load_config(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """전체 설정 로드
        
        Args:
            environment: 환경 이름 (development, production 등)
                        None이면 FLASK_ENV 환경 변수 사용
        
        Returns:
            완전한 설정 딕셔너리
        """
        # 환경 결정
        if environment is None:
            environment = os.getenv('FLASK_ENV', 'development')
        
        logger.info(f"Loading config for environment: {environment}")
        
        # 1. 기본 설정 로드
        config = self.load_yaml_file("default.yaml")
        
        # 2. 환경별 설정 오버라이드
        env_config = self.load_yaml_file(f"{environment}.yaml")
        if env_config:
            config = self.deep_merge(config, env_config)
        
        # 3. 환경 변수 오버라이드
        config = self.apply_env_overrides(config)
        
        return config