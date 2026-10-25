"""风险汇总 + 中文摘要 + 审批关注点 + 回写评论生成(确定性,可单测)。"""
from app.enums import RISK_LEVEL_ZH, ExtractStatus, RiskLevel

_SCORE = {RiskLevel.HIGH.value: 3, RiskLevel.MEDIUM.value: 2, RiskLevel.LOW.value: 1}


def compute_risk_level(hits: list[dict]) -> str:
    """总风险等级判定(保守原则):高命中≥1 → 高;中命中≥3 → 高;中1~2 → 中;仅低 → 低。"""
    high = sum(1 for h in hits if h.get("risk_level") == RiskLevel.HIGH.value)
    medium = sum(1 for h in hits if h.get("risk_level") == RiskLevel.MEDIUM.value)
    if high >= 1 or medium >= 3:
        return "高"
    if medium >= 1:
        return "中"
    return "低"


def build_summary(basic_info: dict, hits: list[dict], overall_level: str) -> str:
    """中文摘要:整体合同风险总结。"""
    contract_no = (basic_info.get("contract_no") or {}).get("value") or "未提取到"
    high = sum(1 for h in hits if h.get("risk_level") == RiskLevel.HIGH.value)
    medium = sum(1 for h in hits if h.get("risk_level") == RiskLevel.MEDIUM.value)
    low = sum(1 for h in hits if h.get("risk_level") == RiskLevel.LOW.value)
    parts = [
        f"本合同(编号 {contract_no})经自动审查共命中 {len(hits)} 项风险规则"
        f"(高风险 {high} 项、中风险 {medium} 项、低风险 {low} 项),总体风险等级为【{overall_level}】。"
    ]
    if hits:
        names = "、".join(h["rule_name"] for h in hits[:3])
        parts.append(f"主要风险集中在:{names}。")
    else:
        parts.append("未发现明显风险点。")
    missing = [f["label"] for f in basic_info.values() if f.get("status") != ExtractStatus.EXTRACTED.value]
    if missing:
        parts.append(f"另有 {len(missing)} 项关键信息未提取到({'、'.join(missing)}),建议审批前重点关注。")
    return "".join(parts)


def build_focus_points(hits: list[dict]) -> list[dict]:
    """审批关注点:每条命中生成一条,末条为固定人工复核提示。"""
    points = []
    for hit in hits:
        evidence = (hit.get("evidence_text") or "").strip()
        if len(evidence) > 60:
            evidence = evidence[:60] + "…"
        points.append({
            "rule_code": hit.get("rule_code"),
            "rule_name": hit.get("rule_name"),
            "risk_level": hit.get("risk_level"),
            "focus": f"请确认:{evidence};建议:{hit.get('suggestion_text') or '人工复核'}",
        })
    points.append({
        "rule_code": None,
        "rule_name": "通用提示",
        "risk_level": None,
        "focus": "本意见为自动审查结果,请结合业务实际复核合同原文后再行审批",
    })
    return points


def build_comment_text(basic_info: dict, overall_level: str, summary: str,
                       hits: list[dict], focus_points: list[dict]) -> str:
    """回写评论区的内容模板(保存前可在调用端人工编辑)。"""

    def bv(key: str) -> str:
        rec = basic_info.get(key)
        if rec and rec.get("status") == ExtractStatus.EXTRACTED.value:
            return str(rec.get("value"))
        return "未提取到"

    lines = [
        "【合同自动审查意见】(由审查工具生成,供法务参考,请结合原文复核)",
        "",
        "一、基本信息",
        f"合同名称:{bv('contract_title')}　　合同编号:{bv('contract_no')}",
        f"签约主体:{bv('our_party')}　　对方名称:{bv('counterparty')}",
        f"合同金额:{bv('amount')} {bv('currency')}　　有效期:{bv('effective_date')} 至 {bv('expiry_date')}",
        "",
        f"二、总体风险等级:【{overall_level}】",
        "",
        "三、审查摘要",
        summary,
        "",
        "四、风险命中明细",
    ]
    for i, hit in enumerate(hits, 1):
        zh = RISK_LEVEL_ZH.get(hit.get("risk_level"), hit.get("risk_level"))
        pos = f"({hit.get('evidence_position')})" if hit.get("evidence_position") else ""
        lines.append(f"{i}.【{zh}】{hit['rule_name']} —— {hit.get('evidence_text') or ''}{pos}")
        if hit.get("suggestion_text"):
            lines.append(f"　 建议:{hit['suggestion_text']}")
    lines += [
        "",
        "五、审批关注点",
    ]
    for i, fp in enumerate(focus_points, 1):
        lines.append(f"{i}. {fp['focus']}")
    lines += [
        "",
        "六、说明",
        "- 本意见为自动审查结果,命中证据位置以“第X条/第X页”标注,可对照原文复核;",
        "- 如对审查结论有异议,可在管理页停用对应规则后重新审查。",
    ]
    return "\n".join(lines)
