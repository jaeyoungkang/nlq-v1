"""
Authentication 데이터 모델
사용자, 세션 등 인증 관련 데이터 클래스 정의
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """사용자 데이터 모델"""
    user_id: str
    email: str
    name: str
    picture: str
    is_authenticated: bool = False
    email_verified: bool = False


@dataclass
class UserSession:
    """사용자 세션 데이터 모델"""
    session_id: str
    user_id: str
    user_email: str
    created_at: datetime
    last_activity: datetime
    is_active: bool = True


def dict_to_user(user_dict: dict) -> User:
    """딕셔너리를 User 객체로 변환"""
    return User(
        user_id=user_dict.get('user_id', ''),
        email=user_dict.get('email', ''),
        name=user_dict.get('name', ''),
        picture=user_dict.get('picture', ''),
        is_authenticated=user_dict.get('is_authenticated', False),
        email_verified=user_dict.get('email_verified', False)
    )


def user_to_dict(user: User) -> dict:
    """User 객체를 딕셔너리로 변환"""
    return {
        'user_id': user.user_id,
        'email': user.email,
        'name': user.name,
        'picture': user.picture,
        'is_authenticated': user.is_authenticated,
        'email_verified': user.email_verified
    }