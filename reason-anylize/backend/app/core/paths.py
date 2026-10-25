"""文件存储路径管理(需求文档第 8 节): uploads/ exports/ workspace 按 {user_id}/{conversation_id} 组织,含路径穿越防护。"""

import re
import shutil
from pathlib import Path

from app.config import settings
from app.core.exceptions import PathTraversalError

STORAGE_ROOT = Path(settings.storage_root).resolve()


def uploads_dir(user_id: int, conversation_id: int) -> Path:
    return STORAGE_ROOT / "uploads" / str(user_id) / str(conversation_id)


def exports_dir(user_id: int, conversation_id: int) -> Path:
    return STORAGE_ROOT / "exports" / str(user_id) / str(conversation_id)


def workspace_dir(user_id: int, conversation_id: int) -> Path:
    return STORAGE_ROOT / "workspace" / str(user_id) / str(conversation_id)


def conversation_dirs(user_id: int, conversation_id: int) -> list[Path]:
    return [uploads_dir(user_id, conversation_id), exports_dir(user_id, conversation_id), workspace_dir(user_id, conversation_id)]


def ensure_conversation_dirs(user_id: int, conversation_id: int) -> None:
    for d in conversation_dirs(user_id, conversation_id):
        d.mkdir(parents=True, exist_ok=True)


def remove_conversation_dirs(user_id: int, conversation_id: int) -> None:
    for d in conversation_dirs(user_id, conversation_id):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def safe_join(base: Path, rel: str) -> Path:
    """在 base 目录内解析相对路径,禁止穿越(..、绝对路径、盘符、空字节)。"""
    rel = (rel or "").replace("\\", "/")
    if "\x00" in rel:
        raise PathTraversalError()
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise PathTraversalError()
    target = (base / rel).resolve()
    base_resolved = base.resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise PathTraversalError()
    return target
