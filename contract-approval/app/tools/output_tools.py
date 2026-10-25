"""工具 6-7:save_review_result / write_approval_comment。"""
import json

from app.adapters.factory import get_approval_adapter
from app.db import SessionLocal
from app.enums import LogType, TaskStatus
from app.models import ApprovalTask, ReviewResult
from app.schemas.common import ToolResult
from app.services import comment_service, log_service, state
from app.utils.errors import StateTransitionError

VALID_OVERALL_LEVELS = ("低", "中", "高")


def save_review_result(case_id: int, overall_risk_level: str, summary_text: str,
                       focus_points_json: str, comment_text: str) -> dict:
    """工具6:保存审查结果、命中规则和摘要信息;任务 → done。"""
    if overall_risk_level not in VALID_OVERALL_LEVELS:
        return ToolResult(success=False,
                          error=f"overall_risk_level 取值非法: {overall_risk_level},可选 低/中/高").model_dump()
    try:
        points = json.loads(focus_points_json)
        if not isinstance(points, list):
            raise ValueError("应为 JSON 数组")
    except Exception as e:
        return ToolResult(success=False, error=f"focus_points_json 解析失败: {e}").model_dump()

    with SessionLocal() as db:
        task = db.get(ApprovalTask, case_id)
        if task is None:
            return ToolResult(success=False, error=f"任务不存在: {case_id}").model_dump()
        try:
            record = db.query(ReviewResult).filter_by(task_id=task.id).first()
            if record is None:
                record = ReviewResult(task_id=task.id)
                db.add(record)
            record.overall_risk_level = overall_risk_level
            record.summary_text = summary_text
            record.focus_points_json = json.dumps(points, ensure_ascii=False)
            record.comment_text = comment_text
            db.flush()
            state.transition(db, task, TaskStatus.DONE.value)
            log_service.log_info(db, task.id, LogType.SAVE.value,
                                 f"审查结果保存成功 (review_id={record.id},总风险 {overall_risk_level})")
            db.commit()
            return ToolResult(success=True, data={
                "review_id": record.id,
                "task_status": task.task_status,
                "write_status": task.write_status,
            }).model_dump()
        except StateTransitionError as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()


def write_approval_comment(instance_id: str, review_id: int) -> dict:
    """工具7:将最终审查意见写回审批评论区,返回回写结果。失败可重试。"""
    with SessionLocal() as db:
        review = db.get(ReviewResult, review_id)
        if review is None:
            return ToolResult(success=False, error=f"审查结果不存在: {review_id}").model_dump()
        task = db.get(ApprovalTask, review.task_id)
        try:
            success, resp = comment_service.write_comment(db, task, review, get_approval_adapter())
            db.commit()
            return ToolResult(
                success=success,
                data={"write_status": task.write_status, "response": resp},
                error=None if success else resp,
            ).model_dump()
        except StateTransitionError as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
