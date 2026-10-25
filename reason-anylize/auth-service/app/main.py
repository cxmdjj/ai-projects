"""mock OAuth2 授权中心: /oauth/authorize → 登录页 → 签发 code → /oauth/token → /oauth/userinfo。

授权码模式的最小实现,供经营归因分析系统演示对接;测试账号见 db.TEST_USERS。
"""

import json
import os
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.code_store import code_store, token_store
from app.db import AuthUser, SessionLocal, get_db, init_db, verify_password

CLIENTS: dict[str, str] = json.loads(
    os.environ.get("AUTH_CLIENTS", '{"analysis-client": "analysis-client-secret"}')
)
ALLOWED_REDIRECT_PREFIXES: list[str] = [
    p.strip()
    for p in os.environ.get(
        "AUTH_ALLOWED_REDIRECT_PREFIXES",
        "http://localhost:8000/auth/callback,http://127.0.0.1:8000/auth/callback",
    ).split(",")
    if p.strip()
]

app = FastAPI(title="认证中心(mock OAuth2)", version="0.1.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@app.on_event("startup")
def startup() -> None:
    init_db()


def _validate_redirect(redirect_uri: str) -> str | None:
    if not redirect_uri or not any(redirect_uri.startswith(p) for p in ALLOWED_REDIRECT_PREFIXES):
        return None
    return redirect_uri


def _user_view(u: AuthUser) -> dict:
    return {
        "sub": str(u.id),
        "username": u.username,
        "display_name": u.display_name,
        "role": u.role,
        "status": u.status,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return (
        "<html><head><meta charset='utf-8'><title>认证中心</title></head>"
        "<body style='font-family:sans-serif;padding:32px'>"
        "<h2>认证中心(mock OAuth2)</h2>"
        "<p>本服务是经营归因分析系统的演示认证中心,请从业务系统登录入口发起授权登录。</p>"
        "<p><a href='/docs'>接口文档</a></p></body></html>"
    )


@app.get("/oauth/authorize", response_class=HTMLResponse)
def authorize(client_id: str, redirect_uri: str, response_type: str = "code", state: str = "", request: Request = None):
    if client_id not in CLIENTS:
        return HTMLResponse("<h3>未知的 client_id</h3>", status_code=400)
    if response_type != "code":
        return HTMLResponse("<h3>仅支持 response_type=code</h3>", status_code=400)
    if _validate_redirect(redirect_uri) is None:
        return HTMLResponse("<h3>redirect_uri 不在白名单内</h3>", status_code=400)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "test_users": [
                {"username": "admin1", "password": "admin123", "label": "系统管理员"},
                {"username": "analyst1", "password": "analyst123", "label": "分析用户"},
            ],
        },
    )


@app.post("/oauth/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    db: Session = Depends(get_db),
):
    if client_id not in CLIENTS:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    if _validate_redirect(redirect_uri) is None:
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    user = db.query(AuthUser).filter(AuthUser.username == username).first()
    if user is None or user.status != "active" or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "error": "用户名或密码错误",
                "test_users": [
                    {"username": "admin1", "password": "admin123", "label": "系统管理员"},
                    {"username": "analyst1", "password": "analyst123", "label": "分析用户"},
                ],
            },
            status_code=401,
        )
    code = code_store.issue(_user_view(user), client_id, redirect_uri)
    params = urlencode({"code": code, "state": state})
    # 303 See Other: 登录表单是 POST 提交,必须强制浏览器改用 GET 跳回业务系统,
    # 否则 307 会保留 POST 方法打到 backend 的 GET /auth/callback 上(405)
    return RedirectResponse(f"{redirect_uri}?{params}", status_code=303)


@app.post("/oauth/token")
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    redirect_uri: str = Form(...),
):
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if CLIENTS.get(client_id) != client_secret:
        return JSONResponse({"error": "invalid_client"}, status_code=401)
    user = code_store.consume(code, client_id, redirect_uri)
    if user is None:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    access_token, expires_in = token_store.issue(user)
    return {"access_token": access_token, "token_type": "bearer", "expires_in": expires_in}


@app.get("/oauth/userinfo")
def userinfo(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    user = token_store.get(auth.removeprefix("Bearer "))
    if user is None:
        return JSONResponse({"error": "invalid_token"}, status_code=401)
    return user
