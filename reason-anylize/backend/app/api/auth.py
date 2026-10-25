"""认证接入: /auth/login 发起授权、/auth/callback 换令牌建立登录态、/api/auth/me、/api/auth/logout。"""

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import OAUTH_STATE_COOKIE, SESSION_COOKIE, create_access_token, generate_state
from app.core.exceptions import AuthError
from app.database import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter()


@router.get("/auth/login")
def login():
    state = generate_state()
    params = urlencode(
        {
            "client_id": settings.oauth_client_id,
            "redirect_uri": f"{settings.backend_public_url}/auth/callback",
            "response_type": "code",
            "state": state,
        }
    )
    response = Response(
        status_code=302, headers={"Location": f"{settings.auth_service_base_url}/oauth/authorize?{params}"}
    )
    response.set_cookie(
        OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax"
    )
    return response


@router.get("/auth/callback")
@router.post("/auth/callback")  # 兜底: 兼容部分授权中心 307 保留 POST 的跳转
def callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise AuthError("授权回调缺少参数")
    if state != request.cookies.get(OAUTH_STATE_COOKIE):
        raise AuthError("state 校验失败,登录请求已失效")

    # 1. 换取访问令牌
    token_resp = httpx.post(
        f"{settings.auth_service_base_url}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.oauth_client_id,
            "client_secret": settings.oauth_client_secret,
            "redirect_uri": f"{settings.backend_public_url}/auth/callback",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        raise AuthError(f"换取令牌失败: {token_resp.text[:200]}")
    access_token = token_resp.json().get("access_token")

    # 2. 获取用户信息
    userinfo_resp = httpx.get(
        f"{settings.auth_service_base_url}/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        raise AuthError("获取用户信息失败")
    info = userinfo_resp.json()

    # 3. upsert 本地用户
    user = db.query(User).filter(User.external_user_id == str(info["sub"])).first()
    if user is None:
        user = User(
            external_user_id=str(info["sub"]),
            username=info.get("username", ""),
            display_name=info.get("display_name", ""),
            role=info.get("role", "analyst"),
            status=info.get("status", "active"),
        )
        db.add(user)
    else:
        user.display_name = info.get("display_name", user.display_name)
        user.role = info.get("role", user.role)
        user.status = info.get("status", user.status)
    db.commit()
    db.refresh(user)

    # 4. 签发会话 JWT 并跳转前端回调页
    token = create_access_token(user.id, user.external_user_id, user.username, user.role)
    response = Response(
        status_code=302, headers={"Location": f"{settings.frontend_url}/auth/callback"}
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=3600 * settings.jwt_ttl_hours,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


@router.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


@router.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}
