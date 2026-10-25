"""规则模块:规则加载、匹配、命中落库(先删后插)、风险汇总。"""
import json

from app.enums import RuleStatus
from app.models import ReviewRule, RuleHit
from app.rules.aggregator import build_comment_text, build_focus_points, build_summary, compute_risk_level
from app.rules.matchers import match_rule
from app.schemas.review import hit_to_dict
from app.utils.errors import RuleEngineError


def run(db, task, parse) -> dict:
    """执行规则审查,返回完整输出(总风险/命中/摘要/关注点/回写文本)。"""
    rules = db.query(ReviewRule).filter_by(rule_status=RuleStatus.ENABLED.value).all()
    if not rules:
        raise RuleEngineError("无可用规则,请先执行种子规则灌入: python -m scripts.init_db --seed")

    basic_map = {f["field"]: f for f in json.loads(parse.basic_info_json or "[]")}
    clause_map = {c["clause"]: c for c in json.loads(parse.clause_info_json or "[]")}
    pages = [(p["page"], p["text"]) for p in json.loads(parse.pages_json or "[]")]
    context = {
        "full_text": parse.source_text or "",
        "pages": pages,
        "basic": basic_map,
        "clauses": clause_map,
    }

    # 重跑幂等:先删旧命中再插
    db.query(RuleHit).filter_by(task_id=task.id).delete()
    hits = []
    for rule in rules:
        try:
            cfg = json.loads(rule.match_text or "{}")
        except json.JSONDecodeError as e:
            raise RuleEngineError(f"规则 {rule.rule_code} 的 match_text 不是合法 JSON: {e}") from e
        result = match_rule(rule.match_mode, cfg, context)
        if result.matched:
            hit = RuleHit(
                task_id=task.id,
                rule_id=rule.id,
                evidence_text=result.evidence_text,
                evidence_position=result.evidence_position,
            )
            db.add(hit)
            db.flush()
            hits.append(hit_to_dict(hit, rule))

    overall = compute_risk_level(hits)
    summary = build_summary(basic_map, hits, overall)
    focus_points = build_focus_points(hits)
    comment_text = build_comment_text(basic_map, overall, summary, hits, focus_points)
    return {
        "overall_risk_level": overall,
        "hits": hits,
        "summary_text": summary,
        "focus_points": focus_points,
        "comment_text": comment_text,
    }
