"""工具安全: db_query 注入拒绝/行数上限/白名单、file_ops 路径穿越、command_exec 限制。"""

import asyncio

import pytest

from app.models import Scn1Category, Scn1Product, Scn1Click, Scn1Conversion
from app.tools import ToolContext, tool_registry


@pytest.fixture()
def demo_data(db):
    from datetime import date

    db.add(Scn1Category(category_id=1, category_name="家电", parent_id=None, level=1, sort_order=1))
    db.add(Scn1Product(product_id=1, sku_code="S1", product_name="破壁机1", category_id=1, price=299, cost_price=200, brand="b"))
    db.add(Scn1Product(product_id=2, sku_code="S2", product_name="破壁机2", category_id=1, price=259, cost_price=180, brand="b"))
    db.add(Scn1Click(stat_date=date(2026, 9, 1), product_id=1, search_keyword="破壁机", click_cnt=100, click_uv=80))
    db.add(Scn1Conversion(stat_date=date(2026, 9, 1), product_id=1, order_cnt=3, order_uv=3, gmv=900))
    db.commit()
    yield
    for m in (Scn1Conversion, Scn1Click, Scn1Product, Scn1Category):
        db.query(m).delete()
    db.commit()


def _ctx(task_id=1, conversation_id=1, user_id=1):
    return ToolContext(task_id=task_id, conversation_id=conversation_id, user_id=user_id)


def _run(coro):
    return asyncio.run(coro)


def test_db_query_select_ok(demo_data):
    result = _run(tool_registry.execute("db_query", {"sql": "SELECT product_name, price FROM scn1_products ORDER BY price DESC", "purpose": "看价格"}, _ctx()))
    assert result.ok, result.error
    import json

    data = json.loads(result.content)
    assert data["row_count"] == 2
    assert data["rows"][0][0] == "破壁机1"


def test_db_query_rejects_write(demo_data):
    for sql in (
        "DELETE FROM scn1_products",
        "INSERT INTO scn1_products VALUES (1)",
        "UPDATE scn1_products SET price=1",
        "DROP TABLE scn1_products",
        "SELECT * FROM scn1_products; DROP TABLE scn1_products",
    ):
        result = _run(tool_registry.execute("db_query", {"sql": sql, "purpose": "x"}, _ctx()))
        assert not result.ok, sql


def test_db_query_rejects_unknown_table(demo_data):
    result = _run(tool_registry.execute("db_query", {"sql": "SELECT * FROM sqlite_master", "purpose": "x"}, _ctx()))
    assert not result.ok
    assert "白名单" in result.error


def test_db_query_row_limit(demo_data):
    result = _run(tool_registry.execute("db_query", {"sql": "SELECT * FROM scn1_products LIMIT 5000", "purpose": "x"}, _ctx()))
    assert not result.ok
    assert "上限" in result.error
    # 未写 LIMIT 自动补
    result = _run(tool_registry.execute("db_query", {"sql": "SELECT * FROM scn1_products", "purpose": "x"}, _ctx()))
    assert result.ok


def test_file_ops_path_traversal(db, make_conversation, user):
    conv = make_conversation()
    ctx = _ctx(conversation_id=conv.id, user_id=user.id)
    for path in ("../../evil.txt", "..\\..\\evil.txt", "C:/Windows/win.ini", "/etc/passwd", ".."):
        result = _run(tool_registry.execute("file_write", {"path": path, "content": "x"}, ctx))
        assert not result.ok, path
    result = _run(tool_registry.execute("file_read", {"path": "../../../../etc/passwd"}, ctx))
    assert not result.ok


def test_file_ops_roundtrip(db, make_conversation, user):
    conv = make_conversation()
    ctx = _ctx(conversation_id=conv.id, user_id=user.id)
    result = _run(tool_registry.execute("file_write", {"path": "notes/data.csv", "content": "a,b\n1,2"}, ctx))
    assert result.ok, result.error
    result = _run(tool_registry.execute("file_read", {"path": "notes/data.csv"}, ctx))
    assert result.ok and "a,b" in result.content
    result = _run(tool_registry.execute("file_list", {}, ctx))
    assert result.ok and "data.csv" in result.content


def test_command_exec_rejects_forbidden(db, make_conversation, user, monkeypatch):
    from app.core.config_manager import config_manager

    monkeypatch.setattr(config_manager, "is_on", lambda key, default=True: True)  # 打开开关
    conv = make_conversation()
    ctx = _ctx(conversation_id=conv.id, user_id=user.id)
    result = _run(tool_registry.execute("command_exec", {"command": "import os\nos.system('dir')"}, ctx))
    assert not result.ok
    result = _run(tool_registry.execute("command_exec", {"command": "import subprocess\nsubprocess.run('dir')"}, ctx))
    assert not result.ok
    result = _run(tool_registry.execute("command_exec", {"command": "import pip\npip.main()"}, ctx))
    assert not result.ok


def test_command_exec_runs_python(db, make_conversation, user, monkeypatch):
    from app.core.config_manager import config_manager

    monkeypatch.setattr(config_manager, "is_on", lambda key, default=True: True)
    conv = make_conversation()
    ctx = _ctx(conversation_id=conv.id, user_id=user.id)
    result = _run(tool_registry.execute("command_exec", {"command": "print('hello sandbox')"}, ctx))
    assert result.ok, result.error
    assert "hello sandbox" in result.content


def test_tool_disabled_by_feature_switch(demo_data):
    result = _run(tool_registry.execute("command_exec", {"command": "print(1)"}, _ctx()))
    assert not result.ok
    assert "禁用" in result.error
