"""认证链路: 授权跳转、回调换令牌、登录态、登出。"""


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.text = str(payload)
        self._payload = payload

    def json(self):
        return self._payload


def test_login_redirect(client):
    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 302
    assert "oauth/authorize" in r.headers["location"]
    assert "state=" in r.headers["location"]
    assert "oauth_state" in r.cookies


def test_login_flow_with_callback(client, db, monkeypatch):
    # 1. 发起登录拿到 state
    r = client.get("/auth/login", follow_redirects=False)
    state = r.cookies["oauth_state"]

    # 2. 模拟认证中心: 换令牌 + 用户信息
    def fake_token_post(url, **kwargs):
        return _FakeResp(200, {"access_token": "at-1", "token_type": "bearer"})

    def fake_userinfo_get(url, **kwargs):
        return _FakeResp(200, {
            "sub": "42", "username": "cbuser1", "display_name": "回调用户",
            "role": "analyst", "status": "active",
        })

    import httpx

    monkeypatch.setattr(httpx, "post", fake_token_post)
    monkeypatch.setattr(httpx, "get", fake_userinfo_get)

    # 3. 回调
    r = client.get(f"/auth/callback?code=abc&state={state}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:5173/auth/callback"
    assert "session_token" in r.cookies

    # 4. 登录态校验
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 200
    assert r2.json()["username"] == "cbuser1"
    assert r2.json()["role"] == "analyst"


def test_callback_state_mismatch(client):
    r = client.get("/auth/login", follow_redirects=False)
    r2 = client.get("/auth/callback?code=abc&state=wrong-state")
    assert r2.status_code == 401
    assert "state" in r2.json()["detail"]


def test_me_requires_login(client):
    client.cookies.clear()  # 前序测试可能在 session 级 client 上残留 cookie
    assert client.get("/api/auth/me").status_code == 401


def test_logout(auth_client):
    r = auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    # 服务端下发 Max-Age=0 删除指令(真实浏览器会照做;httpx 手动设置的 cookie 不响应删除,模拟浏览器清掉)
    assert "Max-Age=0" in r.headers.get("set-cookie", "")
    auth_client.cookies.clear()
    assert auth_client.get("/api/auth/me").status_code == 401
