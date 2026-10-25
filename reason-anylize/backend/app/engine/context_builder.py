"""多轮上下文拼装: system 提示词 + 历史摘要 + 近期消息 + 附件摘录 + 上一轮结果。"""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import paths
from app.core.config_manager import config_manager
from app.models import AnalysisResult, Attachment, ContextSummary, Message

DATA_DICTIONARY = """
【场景一 · 商品目录优化】
- scn1_categories(类目表): category_id 类目ID / category_name 类目名 / parent_id 父类目ID / level 层级(1-3) / sort_order 排序
- scn1_products(商品表): product_id 商品ID / sku_code SKU / product_name 商品名 / category_id 类目ID / price 售价 / cost_price 成本价 / brand 品牌 / shelf_status 上下架(on/off) / on_shelf_date 上架日期
- scn1_search_exposures(搜索曝光表): stat_date 日期 / product_id / search_keyword 搜索词 / exposure_cnt 曝光次数 / exposure_uv 曝光人数
- scn1_clicks(点击表): stat_date / product_id / search_keyword / click_cnt 点击次数 / click_uv
- scn1_conversions(转化表): stat_date / product_id / order_cnt 订单数 / order_uv 下单人数 / gmv 成交额 / refund_cnt 退款单数

【场景二 · 客户行为分析】
- scn2_customers(用户表): customer_id / city 城市 / age_band 年龄段 / gender 性别 / member_level 会员等级(L1-L4) / register_date 注册日期 / channel 注册渠道(A/B/C)
- scn2_visit_events(访问事件表): customer_id / event_time 访问时间 / page_type 页面类型(home/category/product/cart/order) / channel 渠道 / device_type 设备 / session_id
- scn2_cart_events(加购事件表): customer_id / event_time / product_id / quantity 数量 / unit_price 单价
- scn2_order_events(下单事件表): order_id / customer_id / order_time / order_amount 订单金额 / order_status 状态(paid/refunded/cancelled) / channel 下单渠道
"""

SYSTEM_PROMPT = """你是资深经营分析师,负责围绕用户的业务问题进行多轮归因分析,支持持续追问、补充证据、生成阶段性结论和最终分析报告。当前日期: {date}。

【工作流程】
1. 理解用户问题,必要时使用 db_query 工具查询经营数据库获取数据(只能 SELECT);
2. 结合查询结果与附件资料计算关键指标、整理证据;
3. 给出归因结论、待补充数据、下一步建议;
4. 每轮分析结束时必须调用 submit_analysis_result 工具提交六部分结构化结果(问题定义/关键指标/证据列表/归因结论/待补充数据/下一步建议)。

【数据字典】{data_dictionary}

【证据规范】
- 每条证据必须可溯源: source_type 取 database(查询)/attachment(附件)/workspace_file(临时文件)/text_search(文本检索)/command(命令执行)/llm_inference(推理) 之一,source_name 写明来源表或文件名;
- confidence 按数据可靠程度取 high/medium/low;
- 所有指标必须来自实际查询或附件内容,严禁编造数据。

【输出规范】
- 中文输出;结论先陈述主要归因,再说明影响范围;
- key_metrics 至少 1 项,evidence_list 至少 1 项,next_action_text 至少 2 条;
- 多轮对话中,后续轮次应基于此前结论追问与深化,必要时更新结论。"""


class ContextBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, conversation_id: int, current_input: str) -> list[dict]:
        system = SYSTEM_PROMPT.format(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            data_dictionary=DATA_DICTIONARY,
        )
        system += self._summaries_block(conversation_id)
        system += self._attachment_block(conversation_id)
        system += self._last_result_block(conversation_id)

        messages: list[dict] = [{"role": "system", "content": system}]
        messages += self._history_messages(conversation_id)
        messages.append({"role": "user", "content": current_input})
        return messages

    # ---------- 各拼装块 ----------

    def _summaries_block(self, conversation_id: int) -> str:
        rows = (
            self.db.scalars(
                select(ContextSummary)
                .where(ContextSummary.conversation_id == conversation_id)
                .order_by(ContextSummary.start_seq_no)
            )
            .all()
        )
        if not rows:
            return ""
        blocks = [
            f"[历史对话摘要(第{r.start_seq_no}-{r.end_seq_no}轮)]\n{r.summary_text}" for r in rows
        ]
        return "\n\n【历史对话摘要】\n" + "\n\n".join(blocks)

    def _attachment_block(self, conversation_id: int) -> str:
        max_chars = config_manager.get_int("analysis.attachment_excerpt_chars", 2000)
        atts = (
            self.db.scalars(
                select(Attachment)
                .where(Attachment.conversation_id == conversation_id, Attachment.parse_status == "parsed")
                .order_by(Attachment.id.desc())
                .limit(3)
            )
            .all()
        )
        if not atts:
            return ""
        blocks = []
        for a in atts:
            parsed_file = _parsed_path_of(a)
            text = ""
            if parsed_file is not None and parsed_file.exists():
                text = parsed_file.read_text(encoding="utf-8", errors="ignore")[:max_chars]
            else:
                text = "附件解析文本缺失"
            blocks.append(f"[附件 {a.file_name} 内容摘录]\n{text}")
        return "\n\n【附件资料】\n" + "\n\n".join(blocks)

    def _last_result_block(self, conversation_id: int) -> str:
        result = self.db.scalar(
            select(AnalysisResult)
            .where(AnalysisResult.conversation_id == conversation_id)
            .order_by(AnalysisResult.id.desc())
        )
        if result is None:
            return ""
        compact = {
            "problem_definition": result.problem_definition,
            "key_metrics": json.loads(result.key_metrics_json or "[]"),
            "conclusion_text": result.conclusion_text,
            "missing_data_text": result.missing_data_text,
            "next_action_text": json.loads(result.next_action_text or "[]")[:3],
        }
        return (
            "\n\n【上一轮分析结果(阶段结论)】\n"
            + json.dumps(compact, ensure_ascii=False, indent=2)
            + "\n后续轮次应基于此结论追问、补充证据或更新结论。"
        )

    def _history_messages(self, conversation_id: int) -> list[dict]:
        window = config_manager.get_int("analysis.history_window", 20)
        msgs = (
            self.db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.seq_no.desc())
                .limit(window)
            )
            .all()
        )
        msgs.reverse()
        out: list[dict] = []
        tool_notes: list[str] = []
        last_assistant_idx = -1
        for m in msgs:
            if m.role == "user" and m.message_type == "text":
                out.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                out.append({"role": "assistant", "content": m.content})
                last_assistant_idx = len(out) - 1
            elif m.role == "tool":
                note = f"- {m.tool_name}({m.tool_status or 'done'}): {m.content[:200]}"
                if last_assistant_idx >= 0:
                    base = out[last_assistant_idx]
                    base["content"] = base["content"] + "\n\n[本轮工具执行记录]\n" + note
                else:
                    tool_notes.append(note)
        if tool_notes:
            out.append({"role": "user", "content": "[历史工具执行记录]\n" + "\n".join(tool_notes)})
        return out


def _parsed_path_of(a: Attachment):
    """附件解析文本位置: 与原始文件同目录的 .parsed/{attachment_id}.txt。"""
    stored = paths.STORAGE_ROOT / a.file_path
    return stored.parent / ".parsed" / f"{a.id}.txt"
