"""Web 页面路由(Jinja2 模板渲染)。"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import PROJECT_ROOT

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "web" / "templates"))


def _render(request: Request, name: str, context: dict | None = None) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context or {})


@router.get("/", response_class=HTMLResponse)
def page_todos(request: Request):
    return _render(request, "todos.html")


@router.get("/tasks/{code}", response_class=HTMLResponse)
def page_detail(request: Request, code: str):
    return _render(request, "detail.html", {"code": code})


@router.get("/tasks/{code}/parse", response_class=HTMLResponse)
def page_parse(request: Request, code: str):
    return _render(request, "parse.html", {"code": code})


@router.get("/tasks/{code}/review", response_class=HTMLResponse)
def page_review(request: Request, code: str):
    return _render(request, "review.html", {"code": code})


@router.get("/tasks/{code}/output", response_class=HTMLResponse)
def page_output(request: Request, code: str):
    return _render(request, "output.html", {"code": code})


@router.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request):
    return _render(request, "admin.html")
