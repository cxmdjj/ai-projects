"""FastAPI 入口: 建表、默认配置、恢复中断任务、路由挂载、全局异常处理、运行日志。"""

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, attachment, auth, chat, results, tasks, ws
from app.config import settings
from app.core.config_manager import config_manager
from app.core.exceptions import BizError
from app.database import Base, SessionLocal, engine
from app.models import AnalysisTask  # noqa: F401  确保模型注册进 metadata


def _setup_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        config_manager.ensure_defaults(db)
        from app.services.task_service import TaskService

        recovered = TaskService(db).recover_interrupted()
    _setup_logging()
    logging.getLogger("reason_analyze").info("backend 启动完成,恢复中断任务 %s 个", recovered)
    yield


app = FastAPI(title="经营归因分析系统", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(status_code=exc.code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logging.getLogger("reason_analyze").exception("未处理异常 %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(attachment.router)
app.include_router(tasks.router)
app.include_router(results.router)
app.include_router(admin.router)
app.include_router(ws.router)


@app.get("/")
def root():
    return {"service": "reason-analyze-backend", "version": "0.1.0", "docs": "/docs"}
