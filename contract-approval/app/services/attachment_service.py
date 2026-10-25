"""附件模块:下载落盘、附件元数据保存。"""
import hashlib
import re
import shutil
from pathlib import Path

from app.config import PROJECT_ROOT
from app.enums import DownloadStatus
from app.models import ApprovalAttachment

ATTACHMENT_DIR = PROJECT_ROOT / "data" / "attachments"


def _safe_name(name: str) -> str:
    """清理文件名中的路径非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name or "attachment")


def save_attachment(db, task, attachment_id: str, file_name: str, file_type: str,
                    content: bytes, ocr_text_path: str | None = None) -> ApprovalAttachment:
    """附件落盘(按审批编号分目录)并 upsert 附件记录,返回记录。

    ocr_text_path:审批系统侧存储的预识别文本,随附件一并落盘(降级 OCR 数据源)。
    """
    dir_path = ATTACHMENT_DIR / task.approval_code
    dir_path.mkdir(parents=True, exist_ok=True)
    local_path = dir_path / f"{attachment_id}_{_safe_name(file_name)}"
    local_path.write_bytes(content)
    if ocr_text_path and (file_type or "").lower() in ("jpg", "jpeg", "png", "bmp", "tif", "tiff"):
        shutil.copy(ocr_text_path, local_path.with_suffix(".ocr.json"))

    record = (
        db.query(ApprovalAttachment)
        .filter_by(task_id=task.id, attachment_id=attachment_id)
        .first()
    )
    if record is None:
        record = ApprovalAttachment(task_id=task.id, attachment_id=attachment_id)
        db.add(record)
    record.file_name = file_name
    record.file_type = file_type
    record.file_path = str(local_path)
    record.file_size = len(content)
    record.md5 = hashlib.md5(content).hexdigest()
    record.download_status = DownloadStatus.SUCCESS.value
    record.download_error = None
    db.flush()
    return record


def mark_download_failed(db, task, attachment_id: str, file_name: str, error: str) -> ApprovalAttachment:
    """记录附件下载失败(供 blocked 排查)。"""
    record = (
        db.query(ApprovalAttachment)
        .filter_by(task_id=task.id, attachment_id=attachment_id)
        .first()
    )
    if record is None:
        record = ApprovalAttachment(task_id=task.id, attachment_id=attachment_id, file_name=file_name)
        db.add(record)
    record.download_status = DownloadStatus.FAILED.value
    record.download_error = (error or "")[:255]
    db.flush()
    return record
