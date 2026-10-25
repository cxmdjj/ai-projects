"""认证中心本地库: auth_users(启动时种子两个测试账号)。"""

import hashlib
import os
import secrets
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = os.environ.get("AUTH_DB_URL", "sqlite:///./data/auth.db")

Base = declarative_base()


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(128), nullable=False, default="")
    role = Column(String(32), nullable=False, default="analyst")  # admin / analyst
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return secrets.compare_digest(computed, digest)


if DB_URL.startswith("sqlite"):
    db_path = DB_URL.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# 内置测试账号(演示用,文档中公开)
TEST_USERS = [
    {"username": "admin1", "password": "admin123", "display_name": "系统管理员", "role": "admin"},
    {"username": "analyst1", "password": "analyst123", "display_name": "分析用户", "role": "analyst"},
]


def init_db() -> None:
    from datetime import datetime

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for u in TEST_USERS:
            if db.query(AuthUser).filter(AuthUser.username == u["username"]).first() is None:
                db.add(
                    AuthUser(
                        username=u["username"],
                        password_hash=hash_password(u["password"]),
                        display_name=u["display_name"],
                        role=u["role"],
                        created_at=datetime.now(),
                    )
                )
        db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
