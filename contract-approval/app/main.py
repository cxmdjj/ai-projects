"""FastAPI 应用入口。

启动: uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, tasks, tools
from app.config import PROJECT_ROOT
from app.web import router as web_router

app = FastAPI(title="合同审批自动审查系统", version="0.1.0")

app.include_router(tools.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "app" / "web" / "static")), name="static")
app.include_router(web_router)
