"""工具基础类型。"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolResult:
    ok: bool
    content: str
    summary: str = ""
    error: str = ""

    @staticmethod
    def success(content: str, summary: str = "") -> "ToolResult":
        return ToolResult(ok=True, content=content, summary=summary or content[:100])

    @staticmethod
    def fail(error: str) -> "ToolResult":
        return ToolResult(ok=False, content=f"工具执行失败: {error}", error=error)


@dataclass
class ToolContext:
    """工具执行上下文。"""

    task_id: int
    conversation_id: int
    user_id: int = 0


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    feature_key: str
    handler: Callable[[dict, ToolContext], Awaitable[ToolResult]]
    timeout: float = 30.0

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def enabled_specs(self) -> list[dict]:
        from app.core.config_manager import config_manager

        out = []
        for spec in self._specs.values():
            if config_manager.is_on(spec.feature_key):
                out.append(spec.openai_schema())
        return out

    def is_enabled(self, name: str) -> bool:
        spec = self._specs.get(name)
        if spec is None:
            return False
        from app.core.config_manager import config_manager

        return config_manager.is_on(spec.feature_key)

    async def execute(self, name: str, arguments: dict, ctx: ToolContext) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult.fail(f"未知工具 {name}")
        if not self.is_enabled(name):
            return ToolResult.fail(f"工具 {name} 已被功能开关禁用")
        try:
            return await asyncio.wait_for(spec.handler(arguments, ctx), timeout=spec.timeout)
        except asyncio.TimeoutError:
            return ToolResult.fail(f"工具 {name} 执行超时(>{spec.timeout:.0f}s)")
        except Exception as e:  # noqa: BLE001
            return ToolResult.fail(f"工具 {name} 执行异常: {e}")
