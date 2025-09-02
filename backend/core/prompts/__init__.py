"""
Core Prompts Package
프롬프트 템플릿 관리 시스템
"""

from .manager import PromptManager
import os

# 전역 프롬프트 매니저 인스턴스
prompt_manager = PromptManager()

__all__ = ['PromptManager', 'prompt_manager']