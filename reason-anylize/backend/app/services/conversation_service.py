"""会话服务: 新增/查询/更新/级联删除(DB 记录 + 三目录)。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import paths
from app.core.exceptions import BizError
from app.models import (
    AnalysisResult,
    AnalysisTask,
    Attachment,
    ContextSummary,
    Conversation,
    Message,
    TaskLog,
    WebsocketToken,
    User,
)

DELETE_ORDER = [
    (Attachment, None),
    (AnalysisResult, "conversation_id"),
    (ContextSummary, "conversation_id"),
    (TaskLog, None),  # 任务删除后 task_logs 保留? 随任务删: task_id in 任务集合
    (AnalysisTask, "conversation_id"),
    (Message, "conversation_id"),
    (WebsocketToken, "conversation_id"),
]


class ConversationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user: User, title: str) -> Conversation:
        conv = Conversation(user_id=user.id, title=(title or "新会话").strip()[:256] or "新会话")
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        paths.ensure_conversation_dirs(user.id, conv.id)
        return conv

    def list_for_user(self, user: User) -> list[Conversation]:
        return (
            self.db.scalars(
                select(Conversation)
                .where(Conversation.user_id == user.id, Conversation.status != "deleted")
                .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            )
            .all()
        )

    def get_owned(self, user: User, conversation_id: int) -> Conversation:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user.id or conv.status == "deleted":
            raise BizError("会话不存在或无权访问", 404)
        return conv

    def rename(self, user: User, conversation_id: int, title: str) -> Conversation:
        conv = self.get_owned(user, conversation_id)
        if title and title.strip():
            conv.title = title.strip()[:256]
            self.db.commit()
        return conv

    def archive(self, user: User, conversation_id: int) -> Conversation:
        conv = self.get_owned(user, conversation_id)
        conv.status = "archived"
        self.db.commit()
        return conv

    def delete(self, user: User, conversation_ids: list[int]) -> int:
        """级联删除: 消息/附件/任务/结果/摘要/ws-token 记录 + 磁盘三目录。"""
        deleted = 0
        for cid in conversation_ids:
            conv = self.db.get(Conversation, cid)
            if conv is None or conv.user_id != user.id or conv.status == "deleted":
                continue
            # 先取消运行中任务(异步 cancel,不阻塞)
            running_ids = list(
                self.db.scalars(
                    select(AnalysisTask.id).where(
                        AnalysisTask.conversation_id == cid,
                        AnalysisTask.task_status.in_(["queued", "running"]),
                    )
                ).all()
            )
            for tid in running_ids:
                _cancel_silently(tid)

            task_ids = list(self.db.scalars(select(AnalysisTask.id).where(AnalysisTask.conversation_id == cid)).all())
            self.db.execute(TaskLog.__table__.delete().where(TaskLog.task_id.in_(task_ids))) if task_ids else None
            for model, _ in DELETE_ORDER:
                if model is AnalysisTask:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
                elif model is Attachment:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
                elif model is AnalysisResult:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
                elif model is ContextSummary:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
                elif model is Message:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
                elif model is WebsocketToken:
                    self.db.query(model).filter(model.conversation_id == cid).delete(synchronize_session=False)
            conv.status = "deleted"
            conv.updated_at = datetime.now()
            self.db.commit()
            paths.remove_conversation_dirs(user.id, cid)
            deleted += 1
        return deleted


def _cancel_silently(task_id: int) -> None:
    from app.workers import task_worker

    try:
        task_worker.cancel(task_id)
    except Exception:
        pass
