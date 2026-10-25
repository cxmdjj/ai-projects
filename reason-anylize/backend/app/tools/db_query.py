"""db_query 工具: 只读 SQL 查询(单条 SELECT/WITH、表白名单、行数上限、只读连接)。"""

import asyncio
import json
import re
from pathlib import Path

from app.config import settings
from app.tools.base import ToolContext, ToolResult

MAX_ROWS = 1000
QUERY_TIMEOUT = 10.0
ALLOWED_TABLE_PREFIXES = ("scn1_", "scn2_")
READONLY_SYSTEM_TABLES = {
    "users",
    "conversations",
    "messages",
    "attachments",
    "analysis_tasks",
    "analysis_results",
    "context_summaries",
    "task_logs",
}
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|grant|revoke|truncate|begin|commit|rollback|savepoint)\b",
    re.IGNORECASE,
)
TABLE_RE = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
LIMIT_RE = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)

SPEC = {
    "type": "object",
    "required": ["sql", "purpose"],
    "properties": {
        "sql": {"type": "string", "description": "只读 SQL 查询语句,仅允许单条 SELECT 或 WITH 开头"},
        "purpose": {"type": "string", "description": "本次查询的业务目的"},
    },
}


async def run_db_query(arguments: dict, ctx: ToolContext) -> ToolResult:
    sql = (arguments.get("sql") or "").strip().rstrip(";").strip()
    if not sql:
        return ToolResult.fail("sql 不能为空")
    if not re.match(r"^(select|with)\b", sql, re.IGNORECASE):
        return ToolResult.fail("只允许 SELECT / WITH 开头的只读查询")
    if FORBIDDEN_KEYWORDS.search(sql):
        return ToolResult.fail("查询包含被禁止的写操作或管理关键字")
    if ";" in sql:
        return ToolResult.fail("只允许单条 SQL 语句")

    tables = set(t.lower() for t in TABLE_RE.findall(sql))
    if not tables:
        return ToolResult.fail("无法识别查询涉及的表")
    for t in tables:
        if not (t.startswith(ALLOWED_TABLE_PREFIXES) or t in READONLY_SYSTEM_TABLES):
            return ToolResult.fail(f"表 {t} 不在查询白名单内(仅允许 scn1_*/scn2_* 演示表及部分系统只读表)")

    limit_match = LIMIT_RE.search(sql)
    if limit_match and int(limit_match.group(1)) > MAX_ROWS:
        return ToolResult.fail(f"单次查询行数上限为 {MAX_ROWS}")
    if not limit_match:
        sql = f"{sql} LIMIT {MAX_ROWS}"

    try:
        rows, columns = await asyncio.wait_for(asyncio.to_thread(_execute_readonly, sql), timeout=QUERY_TIMEOUT)
    except asyncio.TimeoutError:
        return ToolResult.fail(f"查询超时(>{QUERY_TIMEOUT:.0f}s),请缩小查询范围或增加过滤条件")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail(f"查询执行失败: {e}")

    truncated = len(rows) >= MAX_ROWS
    content = json.dumps(
        {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "note": f"结果已截断至 {MAX_ROWS} 行,请加 WHERE/聚合条件精确查询" if truncated else "",
        },
        ensure_ascii=False,
        default=str,
    )
    summary = f"db_query 返回 {len(rows)} 行" + ("(已截断)" if truncated else "")
    return ToolResult.success(content, summary)


def _execute_readonly(sql: str) -> tuple[list, list]:
    if settings.database_url.startswith("sqlite"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///")).resolve()
        # WAL 模式下只读连接即可安全并发读
        import sqlite3

        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            cur = conn.cursor()
            cur.execute(sql)
            columns = [d[0] for d in (cur.description or [])]
            return [list(r) for r in cur.fetchall()], columns
        finally:
            conn.close()
    else:
        from app.database import engine

        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            result = conn.exec_driver_sql(sql)
            columns = list(result.keys())
            return [list(r) for r in result.fetchall()], columns
