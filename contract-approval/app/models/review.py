"""review_rules / rule_hits / review_results"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import RiskLevel, RuleStatus


class ReviewRule(Base):
    __tablename__ = "review_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(128), default="")
    risk_level: Mapped[str] = mapped_column(String(8), default=RiskLevel.MEDIUM.value)
    rule_status: Mapped[str] = mapped_column(String(8), default=RuleStatus.ENABLED.value)
    match_mode: Mapped[str] = mapped_column(String(32), default="")
    match_text: Mapped[str] = mapped_column(Text, default="{}")  # JSON 字符串
    suggestion_text: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class RuleHit(Base):
    __tablename__ = "rule_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("review_rules.id"), nullable=False, index=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hit_status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id"), unique=True, nullable=False, index=True)
    overall_risk_level: Mapped[str] = mapped_column(String(8), default="")  # 低/中/高
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
