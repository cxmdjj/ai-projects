"""附件服务: 保存、解析管线(pending→parsing→parsed/failed)、删除、下载、路径校验。"""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import paths
from app.core.exceptions import BizError
from app.database import SessionLocal
from app.models import Attachment, Conversation, TaskLog, User

EXCEL_EXTS = {".xlsx", ".xls"}
CSV_EXTS = {".csv"}
TEXT_EXTS = {".txt", ".md", ".json", ".log", ".py", ".sql"}
PARSE_PREVIEW_ROWS = 500
MAX_EXCERPT_CHARS = 100_000  # 解析文本上限


class AttachmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_owned(self, user: User, attachment_id: int) -> Attachment:
        att = self.db.get(Attachment, attachment_id)
        if att is None:
            raise BizError("附件不存在", 404)
        conv = self.db.get(Conversation, att.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise BizError("附件不存在或无权访问", 404)
        return att

    def save_upload(self, user: User, conversation_id: int, file_name: str, content: bytes) -> Attachment:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user.id or conv.status == "deleted":
            raise BizError("会话不存在或无权访问", 404)
        safe_name = Path(file_name or "unnamed").name  # 去掉路径成分
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        base = paths.uploads_dir(user.id, conversation_id)
        base.mkdir(parents=True, exist_ok=True)
        stored_path = base / stored_name
        stored_path.write_bytes(content)
        att = Attachment(
            conversation_id=conversation_id,
            file_name=safe_name,
            file_path=str(stored_path.relative_to(paths.STORAGE_ROOT)).replace("\\", "/"),
            file_type=Path(safe_name).suffix.lower().lstrip("."),
            file_size=len(content),
            parse_status="pending",
        )
        self.db.add(att)
        self.db.commit()
        self.db.refresh(att)
        return att

    def delete(self, user: User, attachment_id: int) -> None:
        att = self.get_owned(user, attachment_id)
        parsed = self._parsed_path(att)
        try:
            Path(paths.STORAGE_ROOT / att.file_path).unlink(missing_ok=True)
            parsed.unlink(missing_ok=True)
        except Exception:
            pass  # 文件缺失不影响记录删除
        self.db.delete(att)
        self.db.commit()

    def list_for_conversation(self, user: User, conversation_id: int) -> list[Attachment]:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user.id or conv.status == "deleted":
            raise BizError("会话不存在或无权访问", 404)
        return (
            self.db.scalars(
                select(Attachment).where(Attachment.conversation_id == conversation_id).order_by(Attachment.id.desc())
            )
            .all()
        )

    def _parsed_path(self, att: Attachment) -> Path:
        uploads = paths.STORAGE_ROOT / "uploads"
        stored = Path(paths.STORAGE_ROOT / att.file_path)
        return stored.parent / ".parsed" / f"{att.id}.txt"

    # ---------------- 解析管线 ----------------

    def run_parse_pipeline(self, attachment_id: int) -> None:
        """后台解析(在 threadpool 中执行,重活不阻塞事件循环)。"""
        db = SessionLocal()
        try:
            att = db.get(Attachment, attachment_id)
            if att is None:
                return
            att.parse_status = "parsing"
            db.commit()
            text = _extract_text(Path(paths.STORAGE_ROOT / att.file_path), att.file_type)
            parsed = self._parsed_path(att)
            parsed.parent.mkdir(parents=True, exist_ok=True)
            parsed.write_text(text, encoding="utf-8")
            att.parse_status = "parsed"
            db.commit()
            self._notify_parsed(att)
        except Exception as e:  # noqa: BLE001
            att = db.get(Attachment, attachment_id)
            if att is not None:
                att.parse_status = "failed"
                db.commit()
            db.add(
                TaskLog(
                    task_id=None,
                    log_level="error",
                    log_type="attachment",
                    log_content=f"附件解析失败 attachment_id={attachment_id}: {e}",
                )
            )
            db.commit()
            self._notify_parsed(att)
        finally:
            db.close()

    def _notify_parsed(self, att: Attachment | None) -> None:
        if att is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # 后台线程中无事件循环,跳过推送(前端可轮询 /api/attachment/ls 感知)
        try:
            from app.services.ws_manager import ws_manager

            loop.create_task(
                ws_manager.broadcast(
                    att.conversation_id,
                    {
                        "type": "attachment_parsed",
                        "attachment_id": att.id,
                        "parse_status": att.parse_status,
                    },
                )
            )
        except Exception:
            pass


def _extract_text(path: Path, file_type: str) -> str:
    ext = path.suffix.lower()
    if ext in CSV_EXTS:
        import pandas as pd

        df = pd.read_csv(path, nrows=PARSE_PREVIEW_ROWS)
        return df.to_json(orient="records", force_ascii=False, date_format="iso")
    if ext in EXCEL_EXTS:
        import pandas as pd

        df = pd.read_excel(path, nrows=PARSE_PREVIEW_ROWS)
        return df.to_json(orient="records", force_ascii=False, date_format="iso")
    if ext in TEXT_EXTS:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:MAX_EXCERPT_CHARS]
    # 其他类型尝试按文本读取
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:MAX_EXCERPT_CHARS]
    except Exception:
        raise BizError("不支持的文件类型,无法解析", 400)
