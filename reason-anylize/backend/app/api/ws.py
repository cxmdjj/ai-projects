"""WebSocket 实时通道: /api/chat/ws/chat?websocket_token=&conversation_id=

- 鉴权: websocket_tokens 一次性消费 + 会话归属校验
- 客户端消息: chat_message(发送分析请求)/ cancel_task(取消)/ ping(心跳)
- 服务端消息: 8 类标准消息(见 docs/WS_PROTOCOL.md)+ attachment_parsed 扩展事件
"""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Conversation, User, WebsocketToken
from app.services.attachment_service import AttachmentService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.task_service import TaskService
from app.services.ws_manager import ws_manager
from app.workers import task_worker

router = APIRouter()


async def _auth_ws(ws: WebSocket, db: Session) -> tuple[User, Conversation]:
    """校验一次性 token + 会话归属,返回 (user, conversation)。"""
    from app.core.exceptions import AuthError

    token = ws.query_params.get("websocket_token")
    conversation_id_raw = ws.query_params.get("conversation_id")
    if not token or not conversation_id_raw:
        await ws.close(code=4401, reason="缺少连接参数")
        raise AuthError("缺少连接参数")
    try:
        conversation_id = int(conversation_id_raw)
    except ValueError:
        await ws.close(code=4401, reason="conversation_id 非法")
        raise AuthError("conversation_id 非法")

    row = db.query(WebsocketToken).filter(WebsocketToken.token == token).first()
    if row is None or row.consumed_at is not None or row.expires_at < datetime.now():
        await ws.close(code=4401, reason="令牌无效或已过期")
        raise AuthError("令牌无效或已过期")
    row.consumed_at = datetime.now()
    row.conversation_id = conversation_id
    db.commit()

    user = db.get(User, row.user_id)
    conv = db.get(Conversation, conversation_id)
    if user is None or conv is None or conv.user_id != user.id or conv.status == "deleted":
        await ws.close(code=4403, reason="会话不存在或无权访问")
        raise AuthError("会话不存在或无权访问")
    return user, conv


@router.websocket("/api/chat/ws/chat")
async def chat_ws(ws: WebSocket, db: Session = Depends(get_db)):
    try:
        user, conv = await _auth_ws(ws, db)
    except Exception:
        return
    await ws.accept()
    await ws_manager.connect(conv.id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "task_id": None, "error_message": "消息不是合法 JSON"})
                continue
            msg_type = payload.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "chat_message":
                await _handle_chat_message(user, conv.id, payload, ws, db)
            elif msg_type == "cancel_task":
                await _handle_cancel(user, payload, ws, db)
            else:
                await ws.send_json({"type": "error", "task_id": None, "error_message": f"未知消息类型 {msg_type}"})
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(conv.id, ws)


async def _handle_chat_message(user: User, conversation_id: int, payload: dict, ws: WebSocket, db: Session) -> None:
    content = (payload.get("content") or "").strip()
    attachment_ids = [int(a) for a in (payload.get("attachment_ids") or []) if str(a).isdigit()]
    if not content and not attachment_ids:
        await ws.send_json({"type": "error", "task_id": None, "error_message": "问题内容不能为空"})
        return

    message_service = MessageService(db)
    # 1. 用户消息入库(seq_no 会话内有序)
    msg = await message_service.create(conversation_id, "user", content)
    if attachment_ids:
        att_service = AttachmentService(db)
        for aid in attachment_ids:
            try:
                att = att_service.get_owned(user, aid)
                if att.conversation_id == conversation_id and att.message_id is None:
                    att.message_id = msg.id
            except Exception:
                continue
        db.commit()

    # 2. 单任务锁: 一个会话同一时间仅一个运行中任务
    task = TaskService(db).create(conversation_id, user.id, content or "(附件资料)")
    if task is None:
        await ws.send_json(
            {"type": "error", "task_id": None, "error_message": "当前会话已有运行中的分析任务,请等待完成或取消后再提问"}
        )
        return

    # 3. 事件推送 + 拉起 worker(入口事件同时进缓冲,保证断线回放完整)
    start_event = {"type": "message_start", "task_id": task.id, "conversation_id": conversation_id}
    queued_event = {"type": "task_status", "task_id": task.id, "task_status": "queued", "current_step": "pending"}
    ws_manager.push_event(task.id, start_event)
    ws_manager.push_event(task.id, queued_event)
    await ws_manager.broadcast(conversation_id, start_event)
    await ws_manager.broadcast(conversation_id, queued_event)
    asyncio.create_task(task_worker.run(task.id))


async def _handle_cancel(user: User, payload: dict, ws: WebSocket, db: Session) -> None:
    try:
        task_id = int(payload.get("task_id"))
    except (TypeError, ValueError):
        await ws.send_json({"type": "error", "task_id": None, "error_message": "task_id 非法"})
        return
    from app.models import AnalysisTask

    task = db.get(AnalysisTask, task_id)
    if task is None or task.user_id != user.id:
        await ws.send_json({"type": "error", "task_id": task_id, "error_message": "任务不存在或无权操作"})
        return
    task_worker.cancel(task_id)
