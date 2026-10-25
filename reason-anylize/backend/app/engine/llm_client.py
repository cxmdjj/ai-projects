"""LLM 客户端: OpenAI 兼容协议(DeepSeek/Qwen/GLM 等),配置实时读取(热更新);

统一流式 delta 解析器收敛各家格式差异(reasoning_content、tool_calls 分片时序等)。
另有 MockLLMClient 供测试与离线演示(不打真实 API)。
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.core.config_manager import config_manager


class LLMError(Exception):
    pass


@dataclass
class UnifiedDelta:
    content: str = ""
    reasoning: str = ""
    finish_reason: str | None = None
    tool_calls: dict[int, dict] = field(default_factory=dict)  # index -> {id, name, arguments_parts: [str]}


class LLMClient:
    """OpenAI 兼容协议客户端;api_key/base_url/model 每次请求从 ConfigManager 实时读取。"""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._key: str | None = None
        self._base_url: str | None = None

    def _ensure_client(self) -> AsyncOpenAI:
        key = config_manager.llm_api_key()
        base_url = config_manager.get("llm.base_url", "")
        if not key:
            raise LLMError("未配置 llm.api_key,请在管理端「系统配置」中填写并重载,或设置环境变量 LLM_API_KEY")
        if self._client is None or key != self._key or base_url != self._base_url:
            self._client = AsyncOpenAI(api_key=key, base_url=base_url or None)
            self._key, self._base_url = key, base_url
        return self._client

    def _base_kwargs(self) -> dict[str, Any]:
        return {
            "model": config_manager.get("llm.model", "deepseek-chat"),
            "temperature": float(config_manager.get("llm.temperature", "0.2")),
            "max_tokens": int(config_manager.get("llm.max_tokens", "4096")),
            "timeout": float(config_manager.get("llm.timeout", "120")),
        }

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None) -> AsyncIterator[UnifiedDelta]:
        client = self._ensure_client()
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools
        try:
            stream = await client.chat.completions.create(**kwargs)
        except TypeError:
            kwargs.pop("tools", None)
            stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            yield self._parse_chunk(chunk)

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, response_format: dict | None = None) -> dict:
        client = self._ensure_client()
        kwargs = {**self._base_kwargs(), "messages": messages, "stream": False}
        if tools:
            kwargs["tools"] = tools
        try:
            resp = await client.chat.completions.create(**kwargs, response_format=response_format)
        except TypeError:
            # 部分兼容接口不支持 response_format 参数,降级
            resp = await client.chat.completions.create(**kwargs)
        return resp.model_dump()

    @staticmethod
    def _parse_chunk(chunk: Any) -> UnifiedDelta:
        d = UnifiedDelta()
        if not chunk.choices:
            return d
        choice = chunk.choices[0]
        d.finish_reason = getattr(choice, "finish_reason", None) or None
        delta = getattr(choice, "delta", None)
        if delta is None:
            return d
        if getattr(delta, "content", None):
            d.content = delta.content
        if getattr(delta, "reasoning_content", None):
            d.reasoning = delta.reasoning_content
        for tc in getattr(delta, "tool_calls", None) or []:
            idx = getattr(tc, "index", 0) or 0
            entry = d.tool_calls.setdefault(idx, {"id": "", "name": "", "arguments_parts": []})
            if getattr(tc, "id", None):
                entry["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    entry["name"] = fn.name
                if getattr(fn, "arguments", None):
                    entry["arguments_parts"].append(fn.arguments)
        return d


# ============================== Mock 实现(测试/离线演示) ==============================


def mock_text_deltas(text: str, chunk_size: int = 12) -> list[UnifiedDelta]:
    """把一段文本拆成多个 content delta,最后附 finish_reason=stop。"""
    deltas = [
        UnifiedDelta(content=text[i : i + chunk_size])
        for i in range(0, len(text), chunk_size)
    ] or [UnifiedDelta(content="")]
    deltas.append(UnifiedDelta(finish_reason="stop"))
    return deltas


def mock_tool_call_deltas(name: str, arguments: dict, call_id: str = "call_mock_1") -> list[UnifiedDelta]:
    """构造一次工具调用的分片 delta(finish_reason=tool_calls)。"""
    args_json = json.dumps(arguments, ensure_ascii=False)
    half = len(args_json) // 2 or 1
    d1 = UnifiedDelta()
    d1.tool_calls = {0: {"id": call_id, "name": name, "arguments_parts": [args_json[:half]]}}
    d2 = UnifiedDelta()
    d2.tool_calls = {0: {"id": "", "name": "", "arguments_parts": [args_json[half:]]}}
    d3 = UnifiedDelta(finish_reason="tool_calls")
    return [d1, d2, d3]


class MockLLMClient(LLMClient):
    """脚本化回放: chat_stream 每次调用消费脚本中一步;chat 消费 mock_chat_responses 队列。"""

    def __init__(
        self,
        script: list[list[UnifiedDelta]] | None = None,
        chat_responses: list[dict] | None = None,
        stream_delay: float = 0.01,
    ) -> None:
        self.script = list(script or [])
        self.chat_responses = list(chat_responses or [])
        self.stream_delay = stream_delay

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None) -> AsyncIterator[UnifiedDelta]:
        if self.script:
            step = self.script.pop(0)
        else:
            step = mock_text_deltas("(演示模式) 本轮无更多脚本步骤。")
        for d in step:
            if self.stream_delay:
                await asyncio.sleep(self.stream_delay)
            yield d

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, response_format: dict | None = None) -> dict:
        if self.chat_responses:
            return self.chat_responses.pop(0)
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                }
            ]
        }
