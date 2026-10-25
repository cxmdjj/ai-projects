from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import SESSION_COOKIE, decode_access_token
from app.core.exceptions import AuthError
from app.database import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_access_token(token) if token else None
    if not payload:
        raise AuthError()
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise AuthError()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AuthError("需要系统管理员权限")
    return user


def get_own_conversation(conversation_id: int, user: User, db: Session):
    """校验会话归属,返回会话对象。"""
    from app.models import Conversation

    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id or conv.status == "deleted":
        raise AuthError("会话不存在或无权访问")
    return conv
