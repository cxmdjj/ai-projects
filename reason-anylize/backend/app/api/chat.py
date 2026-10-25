"""会话与消息接口: /api/chat/create|delete|update|ls|ls/{id}|ws-token。"""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, WebsocketToken
from app.schemas import ConversationCreate, ConversationDelete, ConversationUpdate
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService

router = APIRouter(prefix="/api/chat")

WS_TOKEN_TTL_SECONDS = 60


def _conversation_view(conv) -> dict:
    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "status": conv.status,
        "last_message_at": conv.last_message_at,
    }


@router.post("/create")
def create_conversation(body: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = ConversationService(db).create(user, body.title)
    return _conversation_view(conv)


@router.post("/delete")
def delete_conversations(body: ConversationDelete, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = ConversationService(db).delete(user, body.conversation_ids)
    return {"deleted": deleted}


@router.post("/update")
def update_conversation(body: ConversationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = ConversationService(db)
    if body.status == "archived":
        conv = service.archive(user, body.conversation_id)
    else:
        conv = service.rename(user, body.conversation_id, body.title or "")
        if body.status == "active" and conv.status == "archived":
            conv.status = "active"
            db.commit()
    return _conversation_view(conv)


@router.get("/ls")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = ConversationService(db).list_for_user(user)
    return {"conversations": [_conversation_view(c) for c in convs]}


@router.get("/ls/{conversation_id}")
def list_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ConversationService(db).get_owned(user, conversation_id)
    messages = MessageService(db).list_with_attachments(conversation_id)
    return {"messages": messages}


@router.post("/ws-token")
def create_ws_token(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """签发一次性 WebSocket 连接令牌(60s 过期,连接时消费)。"""
    token = secrets.token_urlsafe(32)
    db.add(
        WebsocketToken(
            user_id=user.id,
            conversation_id=None,  # 签发时未知;连接时以 URL 参数为准并校验会话归属后回填
            token=token,
            expires_at=datetime.now() + timedelta(seconds=WS_TOKEN_TTL_SECONDS),
        )
    )
    db.commit()
    return {"websocket_token": token, "expires_in": WS_TOKEN_TTL_SECONDS}
