"""上下文摘要压缩: 长对话触发,写入 context_summaries(seq_no 区间)。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config_manager import config_manager
from app.models import ContextSummary, Message

SUMMARIZE_PROMPT = (
    "你是经营分析系统的对话摘要器。请把下面的多轮分析对话压缩为一段结构化摘要(300 字以内),"
    "必须保留: 1) 已确认的业务问题;2) 各轮阶段结论;3) 关键指标及数值;4) 已使用的证据来源与要点;5) 待补充数据清单。"
    "直接输出摘要正文,不要任何前缀。\n\n对话内容:\n{text}"
)


class SummaryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _covered_ranges(self, conversation_id: int) -> list[tuple[int, int]]:
        rows = (
            self.db.scalars(
                select(ContextSummary)
                .where(ContextSummary.conversation_id == conversation_id)
                .order_by(ContextSummary.start_seq_no)
            )
            .all()
        )
        return [(r.start_seq_no, r.end_seq_no) for r in rows]

    def _summaries(self, conversation_id: int) -> list[ContextSummary]:
        return (
            self.db.scalars(
                select(ContextSummary)
                .where(ContextSummary.conversation_id == conversation_id)
                .order_by(ContextSummary.start_seq_no)
            )
            .all()
        )

    async def maybe_compress(self, conversation_id: int, llm) -> None:
        trigger = config_manager.get_int("analysis.summary_trigger_msgs", 30)
        keep = config_manager.get_int("analysis.summary_keep_recent", 12)
        count = self.db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        ) or 0
        if count <= trigger:
            return
        max_seq = self.db.scalar(
            select(func.max(Message.seq_no)).where(Message.conversation_id == conversation_id)
        ) or 0
        target_end = max_seq - keep
        if target_end < 1:
            return
        start = 1
        for s, e in sorted(self._covered_ranges(conversation_id)):
            if start < s:
                break
            start = max(start, e + 1)
        if start > target_end:
            return
        msgs = (
            self.db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.seq_no >= start,
                    Message.seq_no <= target_end,
                )
                .order_by(Message.seq_no)
            )
            .all()
        )
        if not msgs:
            return
        text = "\n".join(
            f"[{m.role}{'/' + m.tool_name if m.tool_name else ''}] {m.content[:2000]}" for m in msgs
        )
        try:
            summary = await self._summarize_with_llm(llm, text)
        except Exception:
            summary = _extractive_summary(text)
        self.db.add(
            ContextSummary(
                conversation_id=conversation_id,
                start_seq_no=start,
                end_seq_no=target_end,
                summary_text=summary,
            )
        )
        self.db.commit()
        self._merge_if_needed(conversation_id)

    async def _summarize_with_llm(self, llm, text: str) -> str:
        messages = [
            {"role": "user", "content": SUMMARIZE_PROMPT.format(text=text[:12000])},
        ]
        resp = await llm.chat(messages)
        content = resp["choices"][0]["message"].get("content") or ""
        return content.strip()[:2000]

    def _merge_if_needed(self, conversation_id: int) -> None:
        """摘要行数超过 5 时合并最旧两行,控制摘要体量。"""
        rows = self._summaries(conversation_id)
        if len(rows) <= 5:
            return
        oldest, second = rows[0], rows[1]
        oldest.summary_text = (oldest.summary_text + "\n\n" + second.summary_text)[:6000]
        oldest.end_seq_no = max(oldest.end_seq_no, second.end_seq_no)
        self.db.delete(second)
        self.db.commit()


def _extractive_summary(text: str) -> str:
    """LLM 不可用时的朴素抽取式摘要。"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return "\n".join(lines[:40])[:2000]
