"""任务/附件的出参序列化。"""
from app.models import ApprovalAttachment, ApprovalTask


def task_to_dict(task: ApprovalTask) -> dict:
    return {
        "id": task.id,
        "approval_code": task.approval_code,
        "approval_title": task.approval_title,
        "applicant_name": task.applicant_name,
        "apply_time": task.apply_time.isoformat() if task.apply_time else None,
        "attachment_count": task.attachment_count,
        "form_data_json": task.form_data_json,
        "task_status": task.task_status,
        "write_status": task.write_status,
        "block_reason": task.block_reason,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def attachment_to_dict(att: ApprovalAttachment) -> dict:
    return {
        "id": att.id,
        "task_id": att.task_id,
        "attachment_id": att.attachment_id,
        "file_name": att.file_name,
        "file_type": att.file_type,
        "file_path": att.file_path,
        "file_size": att.file_size,
        "md5": att.md5,
        "download_status": att.download_status,
        "download_error": att.download_error,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }
