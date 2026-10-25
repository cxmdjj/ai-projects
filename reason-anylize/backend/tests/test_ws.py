"""WebSocket 全链路: ws-token 一次性消费、8 类消息、单任务锁、事件回放、取消。"""

import json

import pytest

from app.engine.llm_client import MockLLMClient, mock_text_deltas, mock_tool_call_deltas
from app.models import AnalysisTask
from app.workers import task_worker

RESULT = {
    "problem_definition": "渠道A转化为什么低",
    "key_metrics": [{"metric_name": "访问下单转化率", "metric_value": "1.0%", "metric_unit": "%", "metric_period": "近60天"}],
    "evidence_list": [{"source_type": "database", "source_name": "scn2_order_events", "evidence_text": "渠道A转化1.0%低于大盘", "related_metric": "访问下单转化率", "confidence": "high"}],
    "conclusion_text": "渠道A用户质量差。",
    "missing_data_text": "缺少投放明细。",
    "next_action_text": ["补充投放明细", "优化渠道A承接页"],
}


def _script_ok():
    return [
        # 一次流式响应: 文本 + 提交结果工具调用
        mock_text_deltas("我先查询渠道转化数据。")[:-1]
        + mock_tool_call_deltas("submit_analysis_result", RESULT),
    ]


def test_ws_token_single_use(auth_client, db, make_conversation):
    conv = make_conversation()
    token = auth_client.post("/api/chat/ws-token").json()["websocket_token"]

    from app.models import WebsocketToken

    row = db.query(WebsocketToken).filter(WebsocketToken.token == token).first()
    assert row is not None and row.consumed_at is None

    try:
        with auth_client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={conv.id}") as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
    except Exception:
        pass

    db.refresh(row)
    assert row.consumed_at is not None
    # 第二次连接同一 token → 拒绝
    try:
        with auth_client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={conv.id}"):
            pytest.fail("一次性 token 不应允许二次连接")
    except Exception:
        pass


def test_ws_full_chat_flow(auth_client, db, user, make_conversation, monkeypatch):
    conv = make_conversation()
    token = auth_client.post("/api/chat/ws-token").json()["websocket_token"]
    monkeypatch.setattr(task_worker, "get_llm_client", lambda: MockLLMClient(script=_script_ok()))

    events = []
    with auth_client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={conv.id}") as ws:
        ws.send_json({"type": "chat_message", "content": "渠道A转化为什么低?"})
        for _ in range(50):
            msg = ws.receive_json()
            events.append(msg)
            if msg["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert "message_start" in types
    assert "task_status" in types
    assert "message_delta" in types
    assert "result_ready" in types
    assert "done" in types
    task_id = next(e["task_id"] for e in events if e["type"] == "message_start")

    # 六部分结果可查询
    r = auth_client.get(f"/api/results/{task_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["problem_definition"] == RESULT["problem_definition"]
    assert len(body["next_action_text"]) >= 2
    assert body["result_file_path"]

    # 任务终态 success
    task = db.get(AnalysisTask, task_id)
    assert task.task_status == "success"

    # 历史消息包含 user/assistant 消息
    r = auth_client.get(f"/api/chat/ls/{conv.id}")
    roles = [m["role"] for m in r.json()["messages"]]
    assert "user" in roles and "assistant" in roles


def test_ws_single_task_lock(auth_client, db, make_conversation, monkeypatch):
    conv = make_conversation()
    token = auth_client.post("/api/chat/ws-token").json()["websocket_token"]
    slow = [d for _ in range(50) for d in mock_text_deltas("正在分析……")]
    monkeypatch.setattr(task_worker, "get_llm_client", lambda: MockLLMClient(script=[slow], stream_delay=0.03))

    with auth_client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={conv.id}") as ws:
        ws.send_json({"type": "chat_message", "content": "第一个问题"})
        # 等待 message_start 确保任务已创建
        while True:
            msg = ws.receive_json()
            if msg["type"] == "message_start":
                break
        # 任务运行中再发一条 → 拒绝(单任务锁)
        ws.send_json({"type": "chat_message", "content": "第二个问题"})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "error":
                assert "运行中" in msg["error_message"]
                break
            if msg["type"] == "done":
                pytest.fail("第二个问题不应创建任务")
        # 取消运行中的任务
        task = db.query(AnalysisTask).filter(AnalysisTask.conversation_id == conv.id).order_by(AnalysisTask.id.desc()).first()
        task_id = task.id
        ws.send_json({"type": "cancel_task", "task_id": task_id})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "done":
                break
    db.expire_all()
    assert db.get(AnalysisTask, task_id).task_status == "cancelled"


def test_ws_events_replay(auth_client, db, make_conversation, monkeypatch):
    conv = make_conversation()
    token = auth_client.post("/api/chat/ws-token").json()["websocket_token"]
    monkeypatch.setattr(task_worker, "get_llm_client", lambda: MockLLMClient(script=_script_ok()))

    with auth_client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={conv.id}") as ws:
        ws.send_json({"type": "chat_message", "content": "回放测试"})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "done":
                task_id = msg["task_id"]
                break

    r = auth_client.get(f"/api/tasks/{task_id}/events")
    assert r.status_code == 200
    types = [e["type"] for e in r.json()["events"]]
    assert "message_start" in types and "done" in types
