"""会话 JWT 与 OAuth state 工具。"""

import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

JWT_ALG = "HS256"
SESSION_COOKIE = "session_token"
OAUTH_STATE_COOKIE = "oauth_state"


def create_access_token(user_id: int, external_user_id: str, username: str, role: str) -> str:
    """签发会话 JWT。注意: iat/exp 必须用 UTC 时间,否则 PyJWT 的 iat 校验会按 UTC 解释本地时间导致 ImmatureSignatureError。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "external_user_id": external_user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None


def generate_state() -> str:
    return secrets.token_urlsafe(24)
