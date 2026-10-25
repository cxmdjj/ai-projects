"""工具4:parse_contract_document —— 解析合同文档并返回结构化字段。"""
import json

from app.db import SessionLocal
from app.enums import LogType, ParseStatus, TaskStatus
from app.models import ApprovalAttachment, ContractParse
from app.schemas.common import ToolResult
from app.services import log_service, parse_service, state
from app.utils.errors import EmptyDocumentError, OcrUnavailableError, ParseError, StateTransitionError


def parse_contract_document(document_id: int) -> dict:
    """解析已下载的合同附件(document_id = approval_attachments.id)。

    成功:pending/blocked → parsing → reviewing;
    失败(空文档/OCR失败/解析异常):落 parse_error 记录 + 任务 blocked。
    """
    with SessionLocal() as db:
        attachment = db.get(ApprovalAttachment, document_id)
        if attachment is None:
            return ToolResult(success=False, error=f"附件记录不存在: {document_id}").model_dump()
        task = attachment.task
        try:
            state.transition(db, task, TaskStatus.PARSING.value)
            record, engine = parse_service.parse_attachment(db, task, attachment)
            state.transition(db, task, TaskStatus.REVIEWING.value)
            log_service.log_info(db, task.id, LogType.PARSE.value, f"解析成功({engine}): {attachment.file_name}")
            db.commit()
            return ToolResult(
                success=True,
                data={
                    "parse_id": record.id,
                    "basic_info": json.loads(record.basic_info_json or "[]"),
                    "clauses": json.loads(record.clause_info_json or "[]"),
                    "engine": engine,
                },
            ).model_dump()
        except StateTransitionError as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
        except (EmptyDocumentError, OcrUnavailableError, ParseError) as e:
            db.rollback()
            _save_failed_parse(db, task, isinstance(e, EmptyDocumentError), str(e))
            state.block(db, task, f"解析失败: {e}")
            log_service.log_error(db, task.id, LogType.PARSE.value, str(e))
            db.commit()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            _save_failed_parse(db, task, False, str(e))
            state.block(db, task, f"解析失败: {e}")
            log_service.log_error(db, task.id, LogType.PARSE.value, str(e))
            db.commit()
            return ToolResult(success=False, error=str(e)).model_dump()


def _save_failed_parse(db, task, is_empty: bool, error: str) -> None:
    """解析失败原因必须落库(需求:不允许只返回空结果)。"""
    record = db.query(ContractParse).filter_by(task_id=task.id).first()
    if record is None:
        record = ContractParse(task_id=task.id)
        db.add(record)
    record.parse_status = ParseStatus.EMPTY.value if is_empty else ParseStatus.FAILED.value
    record.parse_error = error[:500]
    db.flush()
