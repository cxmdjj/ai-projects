"""text_search 工具: 会话附件解析文本 + workspace 文件的文本检索(关键词打分,内存实现)。"""

import asyncio
import json
import re

from app.core import paths
from app.tools.base import ToolContext, ToolResult

SNIPPET_HALF = 80
MAX_FILE_CHARS = 200_000
SEARCHABLE_EXTS = {".txt", ".md", ".csv", ".json", ".py", ".sql", ".log"}

SPEC = {
    "type": "object",
    "required": ["query", "source"],
    "properties": {
        "query": {"type": "string", "description": "检索关键词,可包含多个词(空格分隔)"},
        "source": {
            "type": "string",
            "enum": ["attachments", "workspace", "all"],
            "description": "检索来源: attachments(会话附件)/ workspace(临时文件)/ all",
        },
        "top_k": {"type": "integer", "description": "返回条数,默认 5,最大 10"},
    },
}


def _terms(query: str) -> list[str]:
    return [t for t in re.split(r"[\s,;:、。]+", query.strip()) if t]


def _score(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(t.lower()) for t in terms if t)


def _snippet(text: str, terms: list[str]) -> str:
    lowered = text.lower()
    pos = -1
    for t in terms:
        idx = lowered.find(t.lower())
        if idx != -1 and (pos == -1 or idx < pos):
            pos = idx
    if pos == -1:
        return text[: SNIPPET_HALF * 2]
    start = max(0, pos - SNIPPET_HALF)
    return ("..." if start > 0 else "") + text[start : start + SNIPPET_HALF * 2] + "..."


async def _read(path) -> str:
    return await asyncio.to_thread(path.read_text, encoding="utf-8", errors="ignore")


async def run_text_search(arguments: dict, ctx: ToolContext) -> ToolResult:
    query = (arguments.get("query") or "").strip()
    if not query:
        return ToolResult.fail("query 不能为空")
    terms = _terms(query)
    if not terms:
        return ToolResult.fail("query 无有效关键词")
    source = arguments.get("source", "all")
    if source not in ("attachments", "workspace", "all"):
        return ToolResult.fail("source 仅支持 attachments / workspace / all")
    top_k = min(int(arguments.get("top_k", 5) or 5), 10)

    candidates: list[tuple[str, str]] = []  # (source_type, file_name, path)
    if source in ("attachments", "all"):
        uploads_base = paths.STORAGE_ROOT / "uploads" / str(ctx.user_id) / str(ctx.conversation_id)
        for parsed in uploads_base.rglob(".parsed/*.txt"):
            candidates.append(("attachment", parsed.stem, parsed))
    if source in ("workspace", "all"):
        ws = paths.workspace_dir(ctx.user_id, ctx.conversation_id)
        if ws.exists():
            for p in ws.rglob("*"):
                if p.is_file() and p.suffix.lower() in SEARCHABLE_EXTS:
                    candidates.append(("workspace_file", p.name, p))

    results = []
    for source_type, name, path in candidates:
        try:
            text = await _read(path)
        except Exception:
            continue
        text = text[:MAX_FILE_CHARS]
        score = _score(text, terms)
        if score > 0:
            results.append(
                {
                    "file_name": name,
                    "source_type": source_type,
                    "score": score,
                    "snippet": _snippet(text, terms),
                }
            )
    results.sort(key=lambda r: -r["score"])
    results = results[:top_k]
    content = json.dumps({"total_hits": len(results), "results": results}, ensure_ascii=False)
    summary = f"text_search 命中 {len(results)} 个文件" + (f",最高分 {results[0]['score']}" if results else "")
    return ToolResult.success(content, summary)
