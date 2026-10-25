"""file_ops 工具: workspace 临时文件读写(路径穿越防护、大小限制)。"""

import asyncio
import json

from app.core import paths
from app.core.exceptions import PathTraversalError
from app.tools.base import ToolContext, ToolResult

MAX_READ_CHARS = 50_000
MAX_WRITE_CHARS = 1_000_000
LIST_LIMIT = 200
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".py", ".sql", ".log"}

COMMON = {
    "type": "object",
    "required": ["path"],
    "properties": {
        "path": {
            "type": "string",
            "description": "workspace 内的相对文件路径(如 result.csv),禁止绝对路径与 ..",
        },
    },
}

READ_SPEC = {**COMMON}
WRITE_SPEC = {
    "type": "object",
    "required": ["path", "content"],
    "properties": {
        "path": {"type": "string", "description": "workspace 内的相对文件路径,禁止绝对路径与 .."},
        "content": {"type": "string", "description": "要写入的完整文本内容"},
    },
}
LIST_SPEC = {"type": "object", "properties": {}}


def _workspace(ctx: ToolContext):
    return paths.workspace_dir(ctx.user_id, ctx.conversation_id)


async def run_file_read(arguments: dict, ctx: ToolContext) -> ToolResult:
    try:
        target = paths.safe_join(_workspace(ctx), arguments.get("path", ""))
    except PathTraversalError:
        return ToolResult.fail("非法文件路径(仅允许 workspace 内的相对路径)")
    if not target.exists() or not target.is_file():
        return ToolResult.fail(f"文件不存在: {arguments.get('path', '')}")
    try:
        text = await asyncio.to_thread(target.read_text, encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail(f"读取失败: {e}")
    truncated = len(text) > MAX_READ_CHARS
    content = text[:MAX_READ_CHARS] + ("\n...(内容已截断)" if truncated else "")
    return ToolResult.success(content, f"file_read 读取 {arguments.get('path', '')} {len(text)} 字符")


async def run_file_write(arguments: dict, ctx: ToolContext) -> ToolResult:
    try:
        target = paths.safe_join(_workspace(ctx), arguments.get("path", ""))
    except PathTraversalError:
        return ToolResult.fail("非法文件路径(仅允许 workspace 内的相对路径)")
    content = arguments.get("content", "")
    if len(content) > MAX_WRITE_CHARS:
        return ToolResult.fail(f"写入内容超过上限 {MAX_WRITE_CHARS} 字符")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail(f"写入失败: {e}")
    rel = target.relative_to(_workspace(ctx)).as_posix()
    return ToolResult.success(json.dumps({"written": rel, "chars": len(content)}, ensure_ascii=False), f"file_write 已写入 {rel}")


async def run_file_list(arguments: dict, ctx: ToolContext) -> ToolResult:
    base = _workspace(ctx)
    base.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            try:
                rel = p.relative_to(base).as_posix()
            except ValueError:
                continue
            files.append({"path": rel, "size": p.stat().st_size})
            if len(files) >= LIST_LIMIT:
                break
    return ToolResult.success(json.dumps({"files": files}, ensure_ascii=False), f"workspace 共 {len(files)} 个文件")
