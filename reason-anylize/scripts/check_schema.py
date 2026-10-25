"""校验 scripts/init_mysql.sql 与 backend/app/models.py(SQLAlchemy metadata)字段一致,防止双轨漂移。

用法: uv run --project backend python scripts/check_schema.py
退出码 0 = 一致;1 = 存在差异。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base  # noqa: E402
import app.models  # noqa: E402, F401  确保所有模型注册

TABLE_RE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*ENGINE", re.S)
COL_RE = re.compile(r"^\s*`?(\w+)`?\s+", re.M)
DDL_COLUMN_SKIP = {"PRIMARY", "KEY", "UNIQUE", "INDEX", "CONSTRAINT", "FOREIGN"}


def parse_ddl(path: Path) -> dict[str, set[str]]:
    content = path.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for m in TABLE_RE.finditer(content):
        name, body = m.group(1), m.group(2)
        columns = set()
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            first = line.split()[0] if line.split() else ""
            if first.upper() in DDL_COLUMN_SKIP or line.startswith(("PRIMARY KEY", "KEY", "UNIQUE KEY", "INDEX", "CONSTRAINT", "FOREIGN KEY")):
                continue
            cm = COL_RE.match(line)
            if cm:
                columns.add(cm.group(1).strip("`"))
        tables[name] = columns
    return tables


def orm_columns() -> dict[str, set[str]]:
    return {
        table.name: {c.name for c in table.columns}
        for table in Base.metadata.sorted_tables
    }


def main() -> int:
    ddl = parse_ddl(ROOT / "scripts" / "init_mysql.sql")
    orm = orm_columns()
    errors = 0
    all_tables = sorted(set(ddl) | set(orm))
    for table in all_tables:
        ddl_cols = ddl.get(table)
        orm_cols = orm.get(table)
        if ddl_cols is None:
            print(f"[差异] 表 {table}: 仅存在于 models.py,DDL 缺失")
            errors += 1
            continue
        if orm_cols is None:
            print(f"[差异] 表 {table}: 仅存在于 init_mysql.sql,models 缺失")
            errors += 1
            continue
        missing_in_ddl = orm_cols - ddl_cols
        missing_in_orm = ddl_cols - orm_cols
        if missing_in_ddl:
            print(f"[差异] 表 {table}: DDL 缺少列 {sorted(missing_in_ddl)}")
            errors += 1
        if missing_in_orm:
            print(f"[差异] 表 {table}: models 缺少列 {sorted(missing_in_orm)}")
            errors += 1
    if errors == 0:
        print(f"校验通过: {len(all_tables)} 张表的字段在 models.py 与 init_mysql.sql 中完全一致")
        return 0
    print(f"共 {errors} 处差异")
    return 1


if __name__ == "__main__":
    sys.exit(main())
