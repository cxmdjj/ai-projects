"""管理页接口:规则维护、全部任务列表、运行日志查询。"""
import json

from fastapi import APIRouter, Body

from app.db import SessionLocal
from app.models import ApprovalTask, ReviewRule, TaskLog
from app.schemas.approval import task_to_dict
from app.schemas.common import fail, ok
from app.schemas.review import rule_to_dict

router = APIRouter(prefix="/api/admin", tags=["admin"])

_UPDATABLE = ("rule_name", "risk_level", "rule_status", "match_mode", "match_text", "suggestion_text", "description")


@router.get("/rules")
def list_rules():
    with SessionLocal() as db:
        rules = db.query(ReviewRule).order_by(ReviewRule.rule_code).all()
        return ok({"rules": [rule_to_dict(r) for r in rules]})


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, payload: dict = Body(default={})):
    with SessionLocal() as db:
        rule = db.get(ReviewRule, rule_id)
        if rule is None:
            return fail(f"规则不存在: {rule_id}")
        try:
            for key in _UPDATABLE:
                if key in payload:
                    value = payload[key]
                    if key == "match_text":
                        json.loads(value)  # 校验 JSON
                    setattr(rule, key, value)
            db.commit()
            return ok({"rule": rule_to_dict(rule)})
        except Exception as e:
            db.rollback()
            return fail(str(e))


@router.post("/rules")
def create_rule(payload: dict = Body(default={})):
    with SessionLocal() as db:
        try:
            item = {k: payload.get(k) for k in ("rule_code", "rule_name", "risk_level", "match_mode",
                                                "suggestion_text", "description")}
            match_text = payload.get("match_text", "{}")
            json.loads(match_text)
            item["match_text"] = match_text
            item["rule_status"] = payload.get("rule_status", "enabled")
            if db.query(ReviewRule).filter_by(rule_code=item["rule_code"]).first():
                return fail(f"规则编码已存在: {item['rule_code']}")
            rule = ReviewRule(**item)
            db.add(rule)
            db.commit()
            return ok({"rule": rule_to_dict(rule)})
        except Exception as e:
            db.rollback()
            return fail(str(e))


@router.get("/tasks")
def admin_tasks():
    with SessionLocal() as db:
        tasks = db.query(ApprovalTask).order_by(ApprovalTask.id.desc()).all()
        return ok({"tasks": [task_to_dict(t) for t in tasks]})


@router.get("/logs")
def admin_logs(task_id: int | None = None, log_level: str | None = None, limit: int = 100):
    with SessionLocal() as db:
        q = db.query(TaskLog)
        if task_id:
            q = q.filter_by(task_id=task_id)
        if log_level:
            q = q.filter_by(log_level=log_level)
        logs = q.order_by(TaskLog.id.desc()).limit(min(limit, 500)).all()
        return ok({"logs": [{
            "id": l.id,
            "task_id": l.task_id,
            "log_level": l.log_level,
            "log_type": l.log_type,
            "log_content": l.log_content,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in logs]})
