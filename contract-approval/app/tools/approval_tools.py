"""工具 1-3:待办拉取、审批详情、附件下载。"""
import json

from app.adapters.factory import get_approval_adapter
from app.db import SessionLocal
from app.enums import LogType
from app.models import ApprovalTask
from app.schemas.approval import task_to_dict
from app.schemas.common import ToolResult
from app.services import attachment_service, log_service, pull_service, state
from app.utils.errors import ApprovalApiError, AttachmentMissingError


def _block_quietly(db, task, reason: str) -> None:
    """进入阻塞;任务已 done 等无法回退的场合静默跳过。"""
    try:
        state.block(db, task, reason)
    except Exception:
        pass


def list_pending_contract_approvals(limit: int = 50) -> dict:
    """工具1:拉取待处理审批单列表,按审批编号去重保存。"""
    with SessionLocal() as db:
        try:
            adapter = get_approval_adapter()
            approvals = adapter.fetch_pending_approvals(limit)
            result = pull_service.upsert_from_approvals(db, approvals)
            log_service.log_info(
                db, None, LogType.PULL.value,
                f"拉取待办 {len(approvals)} 单,新建 {result['created']} 单,更新 {result['updated']} 单",
            )
            db.commit()
            return ToolResult(
                success=True,
                data={
                    "tasks": [task_to_dict(t) for t in result["tasks"]],
                    "total": len(result["tasks"]),
                    "created": result["created"],
                    "updated": result["updated"],
                },
            ).model_dump()
        except Exception as e:
            db.rollback()
            try:
                log_service.log_error(db, None, LogType.PULL.value, str(e))
                db.commit()
            except Exception:
                db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()


def get_contract_approval(instance_id: str) -> dict:
    """工具2:查询单个审批单详情(审批信息/表单数据/附件信息/当前处理状态)。"""
    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code=instance_id).first()
        try:
            adapter = get_approval_adapter()
            detail = adapter.get_approval_detail(instance_id)
            if task is not None:
                task.form_data_json = json.dumps(detail.form_data, ensure_ascii=False)
                task.attachment_count = len(detail.attachments)
            db.commit()
            return ToolResult(
                success=True,
                data={
                    "approval": {
                        "instance_id": detail.instance_id,
                        "title": detail.title,
                        "applicant": detail.applicant,
                        "apply_time": detail.apply_time.isoformat() if detail.apply_time else None,
                        "form_data": detail.form_data,
                    },
                    "attachments": [a.model_dump() for a in detail.attachments],
                    "task": task_to_dict(task) if task else None,
                },
            ).model_dump()
        except ApprovalApiError as e:
            # 详情获取失败不改变任务状态,记录 error 日志
            db.rollback()
            log_service.log_error(db, task.id if task else None, LogType.PULL.value, str(e))
            db.commit()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()


def download_contract_attachment(instance_id: str, attachment_id: str, file_name: str) -> dict:
    """工具3:下载合同附件,返回本地路径与校验信息(md5/大小)。失败进入 blocked。"""
    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code=instance_id).first()
        if task is None:
            return ToolResult(success=False, error=f"任务不存在: {instance_id},请先拉取待办").model_dump()
        try:
            adapter = get_approval_adapter()
            file_dto = adapter.download_attachment(instance_id, attachment_id)
            record = attachment_service.save_attachment(
                db, task, attachment_id, file_name, file_dto.file_type, file_dto.content, file_dto.ocr_text_path
            )
            log_service.log_info(
                db, task.id, LogType.DOWNLOAD.value,
                f"附件下载成功: {record.file_name} (md5={record.md5}, {record.file_size} 字节)",
            )
            db.commit()
            return ToolResult(
                success=True,
                data={
                    "local_path": record.file_path,
                    "md5": record.md5,
                    "size": record.file_size,
                    "attachment_record_id": record.id,
                },
            ).model_dump()
        except AttachmentMissingError as e:
            db.rollback()
            attachment_service.mark_download_failed(db, task, attachment_id, file_name, str(e))
            _block_quietly(db, task, f"附件缺失: {e}")
            log_service.log_error(db, task.id, LogType.DOWNLOAD.value, str(e))
            db.commit()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            attachment_service.mark_download_failed(db, task, attachment_id, file_name, str(e))
            _block_quietly(db, task, f"附件下载失败: {e}")
            log_service.log_error(db, task.id, LogType.DOWNLOAD.value, str(e))
            db.commit()
            return ToolResult(success=False, error=str(e)).model_dump()
