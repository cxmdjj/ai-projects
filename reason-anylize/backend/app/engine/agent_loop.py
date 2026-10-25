"""AgentLoop: 手动 function-calling 循环 + 流式事件分发(系统核心)。

- 流式 delta → message_delta 事件
- 工具执行 → tool_start / tool_finish 事件
- 结构化结果主路径 = submit_analysis_result 工具(严格 JSON Schema)
- 兜底 = finalize 提示词 + json_object 非流式 + 校验重试
"""

import asyncio
import json

from sqlalchemy.orm import Session

from app.core.config_manager import config_manager
from app.engine.llm_client import LLMError, UnifiedDelta
from app.engine.result_parser import (
    SUBMIT_TOOL_NAME,
    SUBMIT_TOOL_SPEC,
    parse_payload,
    validate_and_normalize,
)
from app.services.message_service import MessageService
from app.tools import ToolContext, tool_registry

FINALIZE_PROMPT = (
    "请基于以上全部对话与工具执行记录,输出本轮归因分析的最终结构化结果。"
    "严格按以下 JSON 结构输出(不要输出任何其他内容):"
    '{"problem_definition": "...", "key_metrics": [{"metric_name": "...", "metric_value": 0, '
    '"metric_unit": "...", "metric_period": "..."}], "evidence_list": [{"source_type": "database", '
    '"source_name": "...", "evidence_text": "...", "related_metric": "...", "confidence": "high"}], '
    '"conclusion_text": "...", "missing_data_text": "...", "next_action_text": ["...", "..."]}'
    "其中 next_action_text 至少 2 条。"
)


class TaskCancelled(Exception):
    pass


class AgentLoop:
    def __init__(
        self,
        llm,
        task_id: int,
        conversation_id: int,
        user_id: int,
        emit,
        cancel_event: asyncio.Event,
        db: Session,
    ) -> None:
        self.llm = llm
        self.task_id = task_id
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.emit = emit
        self.cancel_event = cancel_event
        self.db = db
        self.messages_service = MessageService(db)
        self.tool_ctx = ToolContext(task_id=task_id, conversation_id=conversation_id, user_id=user_id)

    def _check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise TaskCancelled()

    async def run(self, messages: list[dict]) -> dict:
        """执行多轮工具调用循环,返回六部分结果 payload。"""
        max_rounds = config_manager.get_int("analysis.max_tool_rounds", 8)
        tools = tool_registry.enabled_specs() + [SUBMIT_TOOL_SPEC]
        payload: dict | None = None

        for rnd in range(1, max_rounds + 1):
            self._check_cancel()
            await self.emit("task_status", {
                "task_id": self.task_id,
                "task_status": "running",
                "current_step": f"llm_reasoning:{rnd}",
            })
            text, tool_calls = await self._stream_once(messages, tools)
            if text:
                await self.messages_service.create(
                    self.conversation_id, "assistant", text, message_type="text"
                )
            if not tool_calls:
                break  # 模型未调用工具直接结束 → finalize 兜底

            messages.append(
                {
                    "role": "assistant",
                    "content": text or "",
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"]},
                        }
                        for c in tool_calls
                    ],
                }
            )
            submitted: dict | None = None
            for call in tool_calls:
                if call["name"] == SUBMIT_TOOL_NAME:
                    try:
                        raw = json.loads(call["arguments"])
                        submitted = validate_and_normalize(raw)
                        break
                    except Exception as e:  # noqa: BLE001
                        messages.append(self._tool_result(call["id"], f"结构化结果校验失败,请修正后重新提交: {e}"))
                        continue
                await self._execute_tool(messages, call)
            if submitted is not None:
                payload = submitted
                break

        if payload is None:
            payload = await self._finalize(messages)
        return payload

    # ---------- 单轮流式调用 ----------

    async def _stream_once(self, messages: list[dict], tools: list[dict]) -> tuple[str, list[dict]]:
        text_buf: list[str] = []
        tool_frag: dict[int, dict] = {}
        finish = None
        try:
            async for d in self.llm.chat_stream(messages, tools=tools):
                self._check_cancel()
                if d.content:
                    text_buf.append(d.content)
                    await self.emit("message_delta", {"task_id": self.task_id, "delta_text": d.content})
                for idx, frag in d.tool_calls.items():
                    entry = tool_frag.setdefault(idx, {"id": "", "name": "", "arguments_parts": []})
                    if frag.get("id"):
                        entry["id"] = frag["id"]
                    if frag.get("name"):
                        entry["name"] = frag["name"]
                    entry["arguments_parts"].extend(frag.get("arguments_parts", []))
                if d.finish_reason:
                    finish = d.finish_reason
        except TaskCancelled:
            if text_buf:  # 取消时持久化已生成文本,历史回放不丢
                await self.messages_service.create(
                    self.conversation_id, "assistant", "".join(text_buf), message_type="text"
                )
            raise

        text = "".join(text_buf)
        calls = []
        for idx in sorted(tool_frag):
            frag = tool_frag[idx]
            args_raw = "".join(frag["arguments_parts"])
            calls.append(
                {
                    "id": frag["id"] or f"call_{self.task_id}_{idx}",
                    "name": frag["name"] or "",
                    "arguments": args_raw,
                }
            )
        return text, calls

    # ---------- 工具执行 ----------

    async def _execute_tool(self, messages: list[dict], call: dict) -> None:
        if not call["name"]:
            return
        try:
            arguments = json.loads(call["arguments"]) if call["arguments"] else {}
        except json.JSONDecodeError:
            messages.append(self._tool_result(call["id"], f"工具参数 JSON 解析失败: {call['arguments'][:200]}"))
            return
        await self.emit("tool_start", {"task_id": self.task_id, "tool_name": call["name"]})
        await self.emit("task_status", {
            "task_id": self.task_id,
            "task_status": "running",
            "current_step": f"tool_execution:{call['name']}",
        })
        result = await tool_registry.execute(call["name"], arguments, self.tool_ctx)
        await self.messages_service.create(
            self.conversation_id,
            "tool",
            result.content[:4000],
            message_type="tool_result",
            tool_name=call["name"],
            tool_status="success" if result.ok else "error",
        )
        await self.emit("tool_finish", {
            "task_id": self.task_id,
            "tool_name": call["name"],
            "tool_result_summary": result.summary[:500],
        })
        messages.append(self._tool_result(call["id"], result.content))

    @staticmethod
    def _tool_result(call_id: str, content: str) -> dict:
        return {"role": "tool", "tool_call_id": call_id, "content": content}

    # ---------- finalize 兜底 ----------

    async def _finalize(self, messages: list[dict]) -> dict:
        self._check_cancel()
        await self.emit("task_status", {
            "task_id": self.task_id,
            "task_status": "running",
            "current_step": "result_finalize",
        })
        messages.append({"role": "user", "content": FINALIZE_PROMPT})
        last_err = "未返回有效结果"
        for _attempt in range(2):
            self._check_cancel()
            try:
                resp = await self.llm.chat(messages, response_format={"type": "json_object"})
                content = resp["choices"][0]["message"].get("content") or ""
                raw = parse_payload(content)
                return validate_and_normalize(raw)
            except LLMError:
                raise
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                messages.append(
                    {"role": "user", "content": f"上一条结果校验失败({last_err}),请严格按 JSON 结构重新输出完整结果。"}
                )
        raise LLMError(f"结构化结果生成失败: {last_err}")
