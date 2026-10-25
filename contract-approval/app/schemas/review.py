"""审查结果结构:规则命中与审查结论。"""
from app.models import ReviewRule, RuleHit


def rule_to_dict(rule: ReviewRule) -> dict:
    return {
        "id": rule.id,
        "rule_code": rule.rule_code,
        "rule_name": rule.rule_name,
        "risk_level": rule.risk_level,
        "rule_status": rule.rule_status,
        "match_mode": rule.match_mode,
        "match_text": rule.match_text,
        "suggestion_text": rule.suggestion_text,
        "description": rule.description,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def hit_to_dict(hit: RuleHit, rule: ReviewRule | None = None) -> dict:
    return {
        "id": hit.id,
        "task_id": hit.task_id,
        "rule_id": hit.rule_id,
        "rule_code": rule.rule_code if rule else None,
        "rule_name": rule.rule_name if rule else None,
        "risk_level": rule.risk_level if rule else None,
        "evidence_text": hit.evidence_text,
        "evidence_position": hit.evidence_position,
        "hit_status": hit.hit_status,
        "suggestion_text": rule.suggestion_text if rule else None,
    }
