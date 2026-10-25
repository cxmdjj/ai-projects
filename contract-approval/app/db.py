"""数据库引擎与会话。SQLite 默认,可通过配置切换 MySQL。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import PROJECT_ROOT, settings


class Base(DeclarativeBase):
    pass


def _resolve_db_url(url: str) -> str:
    """将相对路径的 sqlite url 解析到项目根目录。"""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        abs_path = (PROJECT_ROOT / rel).as_posix()
        return f"sqlite:///{abs_path}"
    return url


DB_URL = _resolve_db_url(settings["db"]["url"])
_IS_SQLITE = DB_URL.startswith("sqlite")

if _IS_SQLITE:
    # 确保 data 目录存在
    from pathlib import Path

    db_path = Path(DB_URL.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
