"""comment_logs / task_logs"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CommentLog(Base):
    __tablename__ = "comment_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False, index=True)
    write_status: Mapped[str] = mapped_column(String(16), default="")
    write_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("approval_tasks.id"), nullable=True)
    log_level: Mapped[str] = mapped_column(String(8), default="info")
    log_type: Mapped[str] = mapped_column(String(16), default="")
    log_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
