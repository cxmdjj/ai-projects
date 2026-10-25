"""消息服务: seq_no 顺序控制与消息入库。"""

import asyncio
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attachment, Message


class MessageService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def get_seq_lock(conversation_id: int) -> asyncio.Lock:
        return _seq_locks[conversation_id]

    async def next_seq_no(self, conversation_id: int) -> int:
        async with self.get_seq_lock(conversation_id):
            max_seq = self.db.scalar(
                select(func.max(Message.seq_no)).where(Message.conversation_id == conversation_id)
            )
            return (max_seq or 0) + 1

    async def create(
        self,
        conversation_id: int,
        role: str,
        content: str,
        message_type: str = "text",
        tool_name: str | None = None,
        tool_status: str | None = None,
        seq_no: int | None = None,
    ) -> Message:
        if seq_no is None:
            seq_no = await self.next_seq_no(conversation_id)
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            message_type=message_type,
            content=content,
            tool_name=tool_name,
            tool_status=tool_status,
            seq_no=seq_no,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def touch_last_message_at(self, conversation_id: int) -> None:
        from datetime import datetime

        from app.models import Conversation

        conv = self.db.get(Conversation, conversation_id)
        if conv is not None:
            conv.last_message_at = datetime.now()
            self.db.commit()

    def list_with_attachments(self, conversation_id: int) -> list[dict]:
        msgs = (
            self.db.scalars(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq_no)
            )
            .all()
        )
        atts = self.db.scalars(
            select(Attachment).where(Attachment.conversation_id == conversation_id)
        ).all()
        by_msg: dict[int, list[dict]] = defaultdict(list)
        for a in atts:
            if a.message_id is not None:
                by_msg[a.message_id].append(_attachment_view(a))
        return [
            {
                "message_id": m.id,
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "tool_name": m.tool_name,
                "tool_status": m.tool_status,
                "seq_no": m.seq_no,
                "attachments": by_msg.get(m.id, []),
                "created_at": m.created_at,
            }
            for m in msgs
        ]

    def count(self, conversation_id: int) -> int:
        return (
            self.db.scalar(select(func.count(Message.id)).where(Message.conversation_id == conversation_id)) or 0
        )


def _attachment_view(a: Attachment) -> dict:
    return {
        "attachment_id": a.id,
        "file_name": a.file_name,
        "file_type": a.file_type,
        "file_size": a.file_size,
        "parse_status": a.parse_status,
    }


_seq_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
