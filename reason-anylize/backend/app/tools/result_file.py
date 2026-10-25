"""result_file 工具: 结果文件生成(写入 exports 目录,供用户下载)。"""

import asyncio
import json
import re
from urllib.parse import quote

from app.core import paths
from app.core.exceptions import PathTraversalError
from app.tools.base import ToolContext, ToolResult

FILE_NAME_RE = re.compile(r"^[A-Za-z0-9_一-龥.\-]{1,80}$")
RESERVED_RE = re.compile(r"^\d+_analysis_result\.")
MAX_CONTENT_CHARS = 5_000_000

SPEC = {
    "type": "object",
    "required": ["file_name", "file_type", "content"],
    "properties": {
        "file_name": {"type": "string", "description": "结果文件名(不含目录),如 调价模拟影响估算.csv"},
        "file_type": {"type": "string", "enum": ["markdown", "html", "csv", "txt"]},
        "content": {"type": "string", "description": "文件完整内容"},
    },
}


async def run_result_file(arguments: dict, ctx: ToolContext) -> ToolResult:
    file_name = (arguments.get("file_name") or "").strip()
    file_type = arguments.get("file_type") or ""
    content = arguments.get("content") or ""
    if not FILE_NAME_RE.match(file_name):
        return ToolResult.fail("文件名不合法(仅允许中英文、数字、下划线、点、连字符,长度 ≤80)")
    if RESERVED_RE.match(file_name):
        return ToolResult.fail("该文件名为系统保留文件名,请换一个")
    if len(content) > MAX_CONTENT_CHARS:
        return ToolResult.fail("文件内容超过上限 500 万字符")
    base = paths.exports_dir(ctx.user_id, ctx.conversation_id)
    base.mkdir(parents=True, exist_ok=True)
    try:
        target = paths.safe_join(base, file_name)
    except PathTraversalError:
        return ToolResult.fail("非法文件路径")
    if target.exists():
        return ToolResult.fail(f"文件 {file_name} 已存在,请换名或删除后重试")
    try:
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail(f"写入失败: {e}")
    rel = target.relative_to(paths.STORAGE_ROOT).as_posix()
    download_url = f"/api/results/{ctx.task_id}/download?file={quote(file_name)}"
    return ToolResult.success(
        json.dumps({"file_path": rel, "download_url": download_url}, ensure_ascii=False),
        f"结果文件已生成: {file_name}",
    )
