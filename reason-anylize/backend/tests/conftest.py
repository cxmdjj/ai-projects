"""测试基础设施: 导入 app 前注入临时目录环境变量(隔离数据库/存储/日志)。"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="reason-analyze-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_ROOT"] = f"{_TMP}/storage"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"
os.environ["LOG_DIR"] = f"{_TMP}/logs"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["BACKEND_PUBLIC_URL"] = "http://localhost:8000"
os.environ["AUTH_SERVICE_BASE_URL"] = "http://localhost:8001"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.auth import create_access_token  # noqa: E402
from app.core.config_manager import config_manager  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def init_config(db):
    from app.database import Base, engine

    Base.metadata.create_all(engine)  # 幂等,不依赖 TestClient lifespan
    config_manager.ensure_defaults(db)
    yield


def _create_user(db, username="analyst1", role="analyst"):
    user = (
        db.query(User).filter(User.username == username).first()
    )
    if user is None:
        user = User(
            external_user_id=f"ext-{username}",
            username=username,
            display_name=username,
            role=role,
            status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture()
def user(db):
    return _create_user(db, "analyst1", "analyst")


@pytest.fixture()
def admin_user(db):
    return _create_user(db, "admin1", "admin")


@pytest.fixture()
def auth_client(client, user):
    client.cookies.clear()
    token = create_access_token(user.id, user.external_user_id, user.username, user.role)
    client.cookies.set("session_token", token)
    yield client
    client.cookies.clear()


@pytest.fixture()
def auth_admin_client(client, admin_user):
    client.cookies.clear()
    token = create_access_token(admin_user.id, admin_user.external_user_id, admin_user.username, admin_user.role)
    client.cookies.set("session_token", token)
    yield client
    client.cookies.clear()


@pytest.fixture()
def make_conversation(auth_client, db, user):
    from app.services.conversation_service import ConversationService

    def _make(title="测试会话"):
        return ConversationService(db).create(user, title)

    return _make
