"""统一返回结构。"""
from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None


def ok(data: dict | None = None) -> dict:
    return ToolResult(success=True, data=data).model_dump()


def fail(error: str) -> dict:
    return ToolResult(success=False, error=error).model_dump()
