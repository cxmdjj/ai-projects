"""附件接口: /api/attachment/upload|delete|get|ls。"""

import asyncio

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import paths
from app.core.exceptions import BizError
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import AttachmentDelete
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/api/attachment")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _attachment_view(att) -> dict:
    return {
        "attachment_id": att.id,
        "conversation_id": att.conversation_id,
        "message_id": att.message_id,
        "file_name": att.file_name,
        "file_type": att.file_type,
        "file_size": att.file_size,
        "parse_status": att.parse_status,
        "created_at": att.created_at,
    }


@router.post("/upload")
async def upload(
    conversation_id: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise BizError("文件超过 20MB 上限")
    service = AttachmentService(db)
    att = service.save_upload(user, conversation_id, file.filename or "unnamed", content)
    # 后台解析管线(threadpool 中跑 pandas 等重活)
    asyncio.create_task(asyncio.to_thread(service.run_parse_pipeline, att.id))
    return {
        "attachment_id": att.id,
        "file_name": att.file_name,
        "file_path": att.file_path,
    }


@router.post("/delete")
def delete(body: AttachmentDelete, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    AttachmentService(db).delete(user, body.attachment_id)
    return {"deleted": body.attachment_id}


@router.get("/get")
def get(attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    att = AttachmentService(db).get_owned(user, attachment_id)
    target = paths.STORAGE_ROOT / att.file_path
    if not target.exists():
        from app.core.exceptions import BizError

        raise BizError("附件文件已丢失", 404)
    return FileResponse(target, filename=att.file_name)


@router.get("/ls")
def ls(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    atts = AttachmentService(db).list_for_conversation(user, conversation_id)
    return {"attachments": [_attachment_view(a) for a in atts]}
