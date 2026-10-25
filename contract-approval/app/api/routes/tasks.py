"""任务查询/重试/回写日志 + Mock 审批系统辅助接口。"""
import json

from fastapi import APIRouter, Body

from app.adapters.factory import get_approval_adapter
from app.db import SessionLocal
from app.models import ApprovalAttachment, ApprovalTask, CommentLog, ContractParse, ReviewResult, ReviewRule, RuleHit
from app.schemas.approval import attachment_to_dict, task_to_dict
from app.schemas.common import fail, ok
from app.schemas.review import hit_to_dict
from app.services import state

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks")
def list_tasks(task_status: str | None = None):
    with SessionLocal() as db:
        q = db.query(ApprovalTask).order_by(ApprovalTask.id)
        if task_status:
            q = q.filter_by(task_status=task_status)
        return ok({"tasks": [task_to_dict(t) for t in q.all()]})


@router.get("/tasks/{code}")
def task_detail(code: str):
    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code=code).first()
        if task is None:
            return fail(f"任务不存在: {code}")
        attachments = db.query(ApprovalAttachment).filter_by(task_id=task.id).all()
        parse = db.query(ContractParse).filter_by(task_id=task.id).first()
        review = db.query(ReviewResult).filter_by(task_id=task.id).first()
        rules = {r.id: r for r in db.query(ReviewRule).all()}
        hits = [hit_to_dict(h, rules.get(h.rule_id)) for h in db.query(RuleHit).filter_by(task_id=task.id).all()]
        logs = db.query(CommentLog).filter_by(task_id=task.id).order_by(CommentLog.id).all()
        return ok({
            "task": task_to_dict(task),
            "form_data": json.loads(task.form_data_json) if task.form_data_json else {},
            "attachments": [attachment_to_dict(a) for a in attachments],
            "parse": {
                "id": parse.id,
                "parse_status": parse.parse_status,
                "parse_error": parse.parse_error,
                "basic_info": json.loads(parse.basic_info_json or "[]"),
                "clauses": json.loads(parse.clause_info_json or "[]"),
                "created_at": parse.created_at.isoformat() if parse and parse.created_at else None,
            } if parse else None,
            "review": {
                "id": review.id,
                "overall_risk_level": review.overall_risk_level,
                "summary_text": review.summary_text,
                "focus_points": json.loads(review.focus_points_json or "[]"),
                "comment_text": review.comment_text,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            } if review else None,
            "hits": hits,
            "comment_logs": [{
                "id": l.id,
                "write_status": l.write_status,
                "write_response_text": l.write_response_text,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            } for l in logs],
        })


@router.post("/tasks/{code}/retry")
def retry_task(code: str, payload: dict = Body(default={})):
    target = payload.get("target_stage", "parsing")
    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code=code).first()
        if task is None:
            return fail(f"任务不存在: {code}")
        try:
            state.retry(db, task, target)
            db.commit()
            return ok({"approval_code": code, "task_status": task.task_status})
        except Exception as e:
            db.rollback()
            return fail(str(e))


@router.post("/mock/add_attachment")
def mock_add_attachment(payload: dict = Body(default={})):
    """模拟审批人在原审批系统补传附件(blocked 重试演示)。"""
    try:
        adapter = get_approval_adapter()
        adapter.add_attachment(
            payload.get("instance_id", ""),
            payload.get("attachment_id", ""),
            payload.get("file_name", ""),
            payload.get("file_type", ""),
            payload.get("local_file", ""),
        )
        return ok({"message": f"已模拟补传附件到 {payload.get('instance_id', '')}"})
    except Exception as e:
        return fail(str(e))


@router.get("/mock/comments")
def mock_comments():
    """查看 Mock 审批系统收到的评论原文(验收回写成功直观可见)。"""
    try:
        adapter = get_approval_adapter()
        return ok({"comments": adapter.get_received_comments()})
    except Exception as e:
        return fail(str(e))
