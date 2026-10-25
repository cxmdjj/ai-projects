"""管理端接口: 配置热更新、功能开关、权限控制。"""


def test_admin_requires_role(auth_client):
    """普通分析用户访问管理端 → 401。"""
    assert auth_client.get("/api/admin/configs").status_code == 401
    assert auth_client.post("/api/admin/reload").status_code == 401


def test_reload_and_configs(auth_admin_client):
    r = auth_admin_client.post("/api/admin/reload")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    r = auth_admin_client.get("/api/admin/configs")
    assert r.status_code == 200
    keys = {c["config_key"] for c in r.json()["configs"]}
    assert "llm.model" in keys and "feature.db_query" in keys


def test_config_hot_update(auth_admin_client, db):
    """PUT 修改配置 → 立即生效(无需重启)。"""
    r = auth_admin_client.put("/api/admin/configs", json={"key": "llm.model", "value": "qwen-plus"})
    assert r.status_code == 200
    from app.core.config_manager import config_manager

    assert config_manager.get("llm.model") == "qwen-plus"
    auth_admin_client.put("/api/admin/configs", json={"key": "llm.model", "value": "deepseek-chat"})
    assert config_manager.get("llm.model") == "deepseek-chat"


def test_feature_toggle(auth_admin_client):
    r = auth_admin_client.get("/api/admin/features")
    assert r.status_code == 200
    assert r.json()["features"]["feature.command_exec"] == "off"
    # 非法取值拒绝
    r = auth_admin_client.put("/api/admin/features", json={"key": "feature.command_exec", "value": "maybe"})
    assert r.json()["status"] == "rejected"
    # 开启 → 工具注入列表变化
    from app.tools import tool_registry

    names_before = {t["function"]["name"] for t in tool_registry.enabled_specs()}
    assert "command_exec" not in names_before
    auth_admin_client.put("/api/admin/features", json={"key": "feature.command_exec", "value": "on"})
    names_after = {t["function"]["name"] for t in tool_registry.enabled_specs()}
    assert "command_exec" in names_after
    auth_admin_client.put("/api/admin/features", json={"key": "feature.command_exec", "value": "off"})


def test_datasource_test(auth_admin_client):
    from app.config import settings

    r = auth_admin_client.post("/api/admin/datasources/test", json={"db_type": "sqlite", "conn": settings.database_url.removeprefix("sqlite:///")})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_logs_endpoint(auth_admin_client):
    r = auth_admin_client.get("/api/admin/logs", params={"lines": 50})
    assert r.status_code == 200
    assert "lines" in r.json()
