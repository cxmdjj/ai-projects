"""approval_tasks / approval_attachments"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import DownloadStatus, TaskStatus, WriteStatus


class ApprovalTask(Base):
    __tablename__ = "approval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    approval_title: Mapped[str] = mapped_column(String(255), default="")
    applicant_name: Mapped[str] = mapped_column(String(64), default="")
    apply_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)
    form_data_json: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    task_status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING.value, index=True)
    write_status: Mapped[str] = mapped_column(String(16), default=WriteStatus.NOT_WRITTEN.value)
    block_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    attachments: Mapped[list["ApprovalAttachment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class ApprovalAttachment(Base):
    __tablename__ = "approval_attachments"
    __table_args__ = (UniqueConstraint("task_id", "attachment_id", name="uk_task_attachment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False, index=True)
    attachment_id: Mapped[str] = mapped_column(String(64), default="")
    file_name: Mapped[str] = mapped_column(String(255), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="")
    file_path: Mapped[str] = mapped_column(String(512), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    md5: Mapped[str] = mapped_column(String(32), default="")
    download_status: Mapped[str] = mapped_column(String(16), default=DownloadStatus.PENDING.value)
    download_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    task: Mapped["ApprovalTask"] = relationship(back_populates="attachments")
