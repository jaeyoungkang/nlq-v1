"""
프롬프트 템플릿 관리 클래스
JSON 파일에서 프롬프트를 로드하고 템플릿 변수를 치환하여 제공
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from string import Template

logger = logging.getLogger(__name__)


class PromptManager:
    """프롬프트 중앙 관리 클래스"""
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        프롬프트 매니저 초기화
        
        Args:
            prompts_dir: 프롬프트 파일들이 위치한 디렉토리 경로
        """
        # prompts 디렉토리 경로 설정
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # 현재 파일의 디렉토리를 기준으로 설정
            self.prompts_dir = Path(__file__).parent
        
        # 프롬프트 캐시
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._file_timestamps: Dict[str, float] = {}
        
        # 캐싱 활성화 여부
        self.enable_cache = True
        
        logger.info(f"✅ 프롬프트 매니저 초기화: {self.prompts_dir}")
        
        # 초기 로드
        self.reload_all_prompts()
    
    def get_prompt(
        self, 
        category: str, 
        template_name: str, 
        fallback_prompt: str = None,
        **variables
    ) -> str:
        """
        프롬프트 템플릿을 로드하고 변수를 치환하여 반환
        
        Args:
            category: 프롬프트 카테고리 (파일명과 동일)
            template_name: 템플릿 이름
            fallback_prompt: 로드 실패 시 사용할 기본 프롬프트
            **variables: 템플릿에 치환할 변수들
            
        Returns:
            변수가 치환된 최종 프롬프트 문자열
            
        Raises:
            PromptLoadError: 프롬프트 로드 실패 시
        """
        try:
            # 프롬프트 데이터 로드
            prompt_data = self._load_prompt_category(category)
            
            if template_name not in prompt_data.get('templates', {}):
                raise KeyError(f"템플릿 '{template_name}'을 찾을 수 없습니다")
            
            template_info = prompt_data['templates'][template_name]
            template_content = template_info['content']
            
            # 변수 치환
            if variables:
                try:
                    # Python string.Template 사용 (안전한 치환)
                    template = Template(template_content)
                    final_prompt = template.safe_substitute(**variables)
                    
                    # 치환되지 않은 변수가 있는지 확인 (개발 시 디버깅용)
                    remaining_vars = set(template.get_identifiers())
                    provided_vars = set(variables.keys())
                    missing_vars = remaining_vars - provided_vars
                    
                    if missing_vars:
                        logger.warning(f"⚠️ 치환되지 않은 변수들: {missing_vars}")
                    
                except (KeyError, ValueError) as e:
                    logger.error(f"❌ 변수 치환 실패: {str(e)}")
                    # 치환 실패 시 원본 템플릿 반환
                    final_prompt = template_content
            else:
                final_prompt = template_content
            
            logger.debug(f"✅ 프롬프트 로드 성공: {category}.{template_name}")
            return final_prompt
            
        except Exception as e:
            logger.error(f"❌ 프롬프트 로드 실패: {category}.{template_name} - {str(e)}")
            
            # Fallback 프롬프트 사용
            if fallback_prompt:
                logger.info(f"🔄 Fallback 프롬프트 사용: {category}.{template_name}")
                return fallback_prompt
            
            # Fallback도 없으면 예외 발생
            raise PromptLoadError(f"프롬프트 로드 실패 및 Fallback 없음: {category}.{template_name}")
    
    def _load_prompt_category(self, category: str) -> Dict[str, Any]:
        """
        특정 카테고리의 프롬프트 파일 로드
        
        Args:
            category: 프롬프트 카테고리
            
        Returns:
            프롬프트 데이터 딕셔너리
        """
        file_path = self.prompts_dir / f"{category}.json"
        
        # 파일 존재 확인
        if not file_path.exists():
            raise FileNotFoundError(f"프롬프트 파일이 존재하지 않습니다: {file_path}")
        
        # 캐시 확인 (파일 수정 시간 기준)
        if self.enable_cache and self._is_cache_valid(category, file_path):
            return self._cache[category]
        
        # 파일 로드
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)
            
            # 스키마 검증
            self._validate_prompt_schema(prompt_data, category)
            
            # 캐시 업데이트
            if self.enable_cache:
                self._cache[category] = prompt_data
                self._file_timestamps[category] = file_path.stat().st_mtime
            
            logger.debug(f"📂 프롬프트 파일 로드: {category}.json")
            return prompt_data
            
        except json.JSONDecodeError as e:
            raise PromptLoadError(f"JSON 파싱 오류: {file_path} - {str(e)}")
        except Exception as e:
            raise PromptLoadError(f"파일 읽기 오류: {file_path} - {str(e)}")
    
    def _is_cache_valid(self, category: str, file_path: Path) -> bool:
        """
        캐시가 유효한지 확인 (파일 수정 시간 기준)
        
        Args:
            category: 카테고리명
            file_path: 파일 경로
            
        Returns:
            캐시 유효성 여부
        """
        if category not in self._cache or category not in self._file_timestamps:
            return False
        
        try:
            current_mtime = file_path.stat().st_mtime
            cached_mtime = self._file_timestamps[category]
            return current_mtime == cached_mtime
        except OSError:
            return False
    
    def _validate_prompt_schema(self, data: Dict[str, Any], category: str) -> None:
        """
        프롬프트 JSON 스키마 검증
        
        Args:
            data: 프롬프트 데이터
            category: 카테고리명
            
        Raises:
            PromptSchemaError: 스키마 검증 실패 시
        """
        required_fields = ['version', 'category', 'templates']
        
        # 필수 필드 확인
        for field in required_fields:
            if field not in data:
                raise PromptSchemaError(f"필수 필드 누락: {field} in {category}.json")
        
        # 카테고리명 일치 확인
        if data['category'] != category:
            logger.warning(f"⚠️ 카테고리명 불일치: 파일={category}, 내용={data['category']}")
        
        # 템플릿 구조 확인
        templates = data['templates']
        if not isinstance(templates, dict):
            raise PromptSchemaError(f"'templates'는 딕셔너리여야 합니다: {category}.json")
        
        # 각 템플릿의 content 필드 확인
        for template_name, template_info in templates.items():
            if not isinstance(template_info, dict):
                raise PromptSchemaError(f"템플릿 '{template_name}'은 딕셔너리여야 합니다")
            
            if 'content' not in template_info:
                raise PromptSchemaError(f"템플릿 '{template_name}'에 'content' 필드가 없습니다")
    
    def list_available_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        사용 가능한 모든 프롬프트 목록 반환
        
        Returns:
            카테고리별 프롬프트 목록
        """
        available_prompts = {}
        
        # prompts 디렉토리의 모든 JSON 파일 스캔
        for json_file in self.prompts_dir.glob("*.json"):
            category = json_file.stem
            
            try:
                prompt_data = self._load_prompt_category(category)
                templates = prompt_data.get('templates', {})
                
                available_prompts[category] = {
                    'version': prompt_data.get('version', 'unknown'),
                    'description': prompt_data.get('description', ''),
                    'templates': list(templates.keys()),
                    'template_details': {
                        name: {
                            'variables': info.get('variables', []),
                            'description': info.get('description', '')
                        }
                        for name, info in templates.items()
                    }
                }
            except Exception as e:
                logger.error(f"❌ 프롬프트 목록 수집 실패: {category} - {str(e)}")
                available_prompts[category] = {'error': str(e)}
        
        return available_prompts
    
    def reload_all_prompts(self) -> None:
        """
        모든 프롬프트 캐시를 지우고 다시 로드
        """
        self._cache.clear()
        self._file_timestamps.clear()
        
        # 사용 가능한 프롬프트 파일들을 미리 로드
        json_files = list(self.prompts_dir.glob("*.json"))
        loaded_count = 0
        
        for json_file in json_files:
            category = json_file.stem
            try:
                self._load_prompt_category(category)
                loaded_count += 1
            except Exception as e:
                logger.error(f"❌ 프롬프트 로드 실패: {category} - {str(e)}")
        
        logger.info(f"🔄 프롬프트 다시 로드 완료: {loaded_count}/{len(json_files)}개 파일")
    
    def reload_category(self, category: str) -> bool:
        """
        특정 카테고리의 프롬프트만 다시 로드
        
        Args:
            category: 다시 로드할 카테고리
            
        Returns:
            로드 성공 여부
        """
        try:
            # 캐시에서 제거
            if category in self._cache:
                del self._cache[category]
            if category in self._file_timestamps:
                del self._file_timestamps[category]
            
            # 다시 로드
            self._load_prompt_category(category)
            logger.info(f"🔄 카테고리 다시 로드 완료: {category}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 카테고리 다시 로드 실패: {category} - {str(e)}")
            return False
    
    def get_prompt_info(self, category: str, template_name: str) -> Dict[str, Any]:
        """
        특정 프롬프트의 메타데이터 반환
        
        Args:
            category: 카테고리명
            template_name: 템플릿명
            
        Returns:
            프롬프트 메타데이터
        """
        try:
            prompt_data = self._load_prompt_category(category)
            template_info = prompt_data['templates'].get(template_name, {})
            
            return {
                'category': category,
                'template_name': template_name,
                'version': prompt_data.get('version', 'unknown'),
                'variables': template_info.get('variables', []),
                'description': template_info.get('description', ''),
                'content_length': len(template_info.get('content', '')),
                'file_path': str(self.prompts_dir / f"{category}.json")
            }
            
        except Exception as e:
            return {'error': str(e)}


# 커스텀 예외 클래스들
class PromptLoadError(Exception):
    """프롬프트 로드 실패 예외"""
    pass


class PromptSchemaError(Exception):
    """프롬프트 스키마 검증 실패 예외"""
    pass