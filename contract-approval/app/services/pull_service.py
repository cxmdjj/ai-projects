"""拉取模块:待办拉取 + 去重保存。"""
from app.models import ApprovalTask


def upsert_from_approvals(db, approvals) -> dict:
    """按 approval_code 唯一键 upsert。

    重复拉取只更新展示字段(标题/申请人/时间/附件数),
    已 done / blocked 任务的状态与回写状态永不回退。
    返回 {"tasks": [...], "created": n, "updated": n}。
    """
    created = updated = 0
    tasks: list[ApprovalTask] = []
    for a in approvals:
        task = db.query(ApprovalTask).filter_by(approval_code=a.instance_id).first()
        if task is None:
            task = ApprovalTask(
                approval_code=a.instance_id,
                approval_title=a.title,
                applicant_name=a.applicant,
                apply_time=a.apply_time,
                attachment_count=a.attachment_count,
            )
            db.add(task)
            created += 1
        else:
            task.approval_title = a.title
            task.applicant_name = a.applicant
            task.apply_time = a.apply_time
            task.attachment_count = a.attachment_count
            updated += 1
        tasks.append(task)
    db.flush()
    return {"tasks": tasks, "created": created, "updated": updated}
