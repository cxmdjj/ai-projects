"""AgentLoop: 手动 function-calling 循环、事件序列、六部分结果、finalize 兜底、取消。"""

import asyncio
import json

import pytest

from app.engine.agent_loop import AgentLoop, TaskCancelled
from app.engine.llm_client import MockLLMClient, mock_text_deltas, mock_tool_call_deltas

VALID_RESULT = {
    "problem_definition": "为什么厨房小家电转化率偏低",
    "key_metrics": [
        {"metric_name": "点击下单转化率", "metric_value": "1.01%", "metric_unit": "%", "metric_period": "近60天"}
    ],
    "evidence_list": [
        {
            "source_type": "database",
            "source_name": "scn1_clicks/scn1_conversions",
            "evidence_text": "厨房小家电点击→下单转化率 1.01%,低于大盘 2.5%",
            "related_metric": "点击下单转化率",
            "confidence": "high",
        }
    ],
    "conclusion_text": "厨房小家电转化偏低,主因价格带偏高。",
    "missing_data_text": "缺少竞品价格数据。",
    "next_action_text": ["补充竞品价格数据", "输出调价模拟"],
}


def _make_loop(llm, db, task_id=1, conversation_id=None, user_id=None, events=None):
    if conversation_id is None or user_id is None:
        from app.models import Conversation, User

        user = db.query(User).first()
        if user is None:
            user = User(external_user_id="ext-t", username="tester", display_name="t", role="analyst", status="active")
            db.add(user)
            db.commit()
            db.refresh(user)
        conv = db.query(Conversation).first()
        if conv is None:
            conv = Conversation(user_id=user.id, title="t")
            db.add(conv)
            db.commit()
            db.refresh(conv)
        conversation_id, user_id = conv.id, user.id

    async def emit(event_type, payload):
        events.append({"type": event_type, **payload}) if events is not None else None

    return AgentLoop(
        llm=llm,
        task_id=task_id,
        conversation_id=conversation_id,
        user_id=user_id,
        emit=emit,
        cancel_event=asyncio.Event(),
        db=db,
    )


@pytest.mark.asyncio
async def test_agent_loop_submit_flow(db):
    events = []
    script = [
        # 一次流式响应: 先输出文本,再调用提交工具(去掉文本步骤尾部的 stop 标记)
        mock_text_deltas("我先查一下类目转化数据。")[:-1]
        + mock_tool_call_deltas("submit_analysis_result", VALID_RESULT),
    ]
    loop = _make_loop(MockLLMClient(script=script), db, events=events)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "分析转化问题"}]
    payload = await loop.run(messages)

    assert payload["problem_definition"].startswith("为什么")
    assert len(payload["key_metrics"]) == 1
    assert len(payload["evidence_list"]) == 1
    assert len(payload["next_action_text"]) >= 2

    types = [e["type"] for e in events]
    assert "message_delta" in types
    assert "task_status" in types
    assert types.count("message_delta") >= 1


@pytest.mark.asyncio
async def test_agent_loop_executes_tools(db):
    """mock 让模型先调用 db_query,再(第二轮)输出文本并提交结果,验证工具执行链路。"""
    events = []
    script = [
        mock_tool_call_deltas("db_query", {"sql": "SELECT product_name, price FROM scn1_products LIMIT 3", "purpose": "看价格"}, call_id="call_demo_1"),
        mock_text_deltas("查询完成,整理结论。")[:-1]
        + mock_tool_call_deltas("submit_analysis_result", VALID_RESULT, call_id="call_demo_2"),
    ]
    loop = _make_loop(MockLLMClient(script=script), db, events=events)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    payload = await loop.run(messages)
    assert payload is not None

    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_finish" in types
    tool_starts = [e for e in events if e["type"] == "tool_start"]
    assert tool_starts[0]["tool_name"] == "db_query"

    # 工具消息落库(历史回放可见)
    from app.models import Message

    tool_msgs = db.query(Message).filter(Message.role == "tool").all()
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_name == "db_query"
    assert tool_msgs[0].tool_status == "success"


@pytest.mark.asyncio
async def test_agent_loop_invalid_submit_retries(db):
    """提交非法结果 → 校验失败反馈 → 第二次提交合法。"""
    bad = dict(VALID_RESULT)
    bad.pop("evidence_list")
    script = [
        mock_tool_call_deltas("submit_analysis_result", bad, call_id="call_bad"),
        mock_tool_call_deltas("submit_analysis_result", VALID_RESULT, call_id="call_good"),
    ]
    loop = _make_loop(MockLLMClient(script=script), db)
    payload = await loop.run([{"role": "system", "content": "s"}, {"role": "user", "content": "q"}])
    assert payload["problem_definition"] == VALID_RESULT["problem_definition"]


@pytest.mark.asyncio
async def test_agent_loop_finalize_fallback(db):
    """模型不调用提交工具,靠 finalize 兜底(json_object 非流式)。"""
    chat_responses = [
        {
            "choices": [
                {"message": {"role": "assistant", "content": json.dumps(VALID_RESULT, ensure_ascii=False)}, "finish_reason": "stop"}
            ]
        }
    ]
    llm = MockLLMClient(script=[mock_text_deltas("我直接说结论,不调用工具。")], chat_responses=chat_responses)
    loop = _make_loop(llm, db)
    payload = await loop.run([{"role": "system", "content": "s"}, {"role": "user", "content": "q"}])
    assert payload["conclusion_text"]


@pytest.mark.asyncio
async def test_agent_loop_next_actions_min_2(db):
    """next_action_text 不足 2 条时自动补齐。"""
    one_action = dict(VALID_RESULT)
    one_action["next_action_text"] = ["唯一一条建议"]
    script = [mock_tool_call_deltas("submit_analysis_result", one_action)]
    loop = _make_loop(MockLLMClient(script=script), db)
    payload = await loop.run([{"role": "system", "content": "s"}, {"role": "user", "content": "q"}])
    assert len(payload["next_action_text"]) >= 2


@pytest.mark.asyncio
async def test_agent_loop_cancel_mid_stream(db):
    """流式中取消: 抛 TaskCancelled 且已生成文本持久化。"""
    deltas = []
    for i in range(30):
        deltas += mock_text_deltas(f"第{i}段分析文本")
    llm = MockLLMClient(script=[deltas], stream_delay=0.02)
    events = []
    cancel_event = asyncio.Event()
    async def emit(event_type, payload):
        events.append({"type": event_type, **payload})
        if len(events) >= 3:  # 收到少量 delta 后触发取消
            cancel_event.set()

    loop = AgentLoop(llm=llm, task_id=1, conversation_id=1, user_id=1, emit=emit, cancel_event=cancel_event, db=db)
    with pytest.raises(TaskCancelled):
        await loop.run([{"role": "system", "content": "s"}, {"role": "user", "content": "q"}])

    from app.models import Message

    partial = db.query(Message).filter(Message.role == "assistant").all()
    assert partial and partial[0].content  # 已生成文本落库
