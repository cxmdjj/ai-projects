"""contract_parses"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import ParseStatus


class ContractParse(Base):
    __tablename__ = "contract_parses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), unique=True, nullable=False, index=True)
    basic_info_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    clause_info_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # [{page, text}],规则命中定位页码用
    parse_status: Mapped[str] = mapped_column(String(16), default=ParseStatus.PENDING.value)
    parse_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
