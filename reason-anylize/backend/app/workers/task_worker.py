"""任务执行器: queued→running→success/failed/cancelled 状态机 + 协作式取消 + 事件推送。

worker 与 WS 连接解耦(断线不终止任务);所有状态流转走 CAS,取消不覆盖终态。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.core.config_manager import config_manager
from app.database import SessionLocal
from app.engine.agent_loop import AgentLoop, TaskCancelled
from app.engine.context_builder import ContextBuilder
from app.engine.llm_client import LLMClient, LLMError, MockLLMClient
from app.models import AnalysisTask
from app.services.message_service import MessageService
from app.services.result_service import ResultService
from app.services.summary_service import SummaryService
from app.services.task_service import TaskService
from app.services.ws_manager import ws_manager

logger = logging.getLogger("reason_analyze.task_worker")

_cancel_events: dict[int, asyncio.Event] = {}


def get_llm_client():
    """按配置实例化 LLM 客户端(openai-compatible / mock)。"""
    provider = config_manager.get("llm.provider", "openai-compatible")
    if provider == "mock":
        return MockLLMClient()
    return LLMClient()


def cancel(task_id: int) -> None:
    """请求取消(协作式): 设置 cancel_event,worker 在检查点响应。"""
    _cancel_events.setdefault(task_id, asyncio.Event()).set()


async def run(task_id: int) -> None:
    cancel_event = _cancel_events.setdefault(task_id, asyncio.Event())
    db = SessionLocal()
    task = db.get(AnalysisTask, task_id)
    if task is None:
        db.close()
        return
    conversation_id = task.conversation_id
    user_id = task.user_id
    task_service = TaskService(db)

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, **payload}
        await ws_manager.broadcast(conversation_id, event)
        ws_manager.push_event(task_id, event)

    async def set_step(step: str) -> None:
        if task_service.cas_update(task_id, ("running",), "running", current_step=step):
            await emit("task_status", {"task_id": task_id, "task_status": "running", "current_step": step})

    try:
        if not task_service.cas_update(
            task_id, ("queued",), "running", current_step="context_assembly", started_at=datetime.now()
        ):
            return
        await emit("task_status", {"task_id": task_id, "task_status": "running", "current_step": "context_assembly"})
        if cancel_event.is_set():
            raise TaskCancelled()

        messages = ContextBuilder(db).build(conversation_id, task.input_text)
        llm = get_llm_client()
        loop = AgentLoop(llm=llm, task_id=task_id, conversation_id=conversation_id, user_id=user_id, emit=emit, cancel_event=cancel_event, db=db)

        timeout = config_manager.get_int("analysis.task_timeout", 600)
        await set_step("llm_reasoning")
        payload = await asyncio.wait_for(loop.run(messages), timeout=timeout)

        if cancel_event.is_set():
            raise TaskCancelled()
        await set_step("result_generation")
        result = ResultService(db).create(task, payload)
        await emit("result_ready", {"task_id": task_id, "result_id": result.id})
        task_service.log(task_id, "info", "task", f"结构化结果已生成 result_id={result.id}")

        await set_step("summary_compression")
        try:
            await SummaryService(db).maybe_compress(conversation_id, llm)
        except Exception as e:  # noqa: BLE001 - 压缩失败不阻塞任务
            task_service.log(task_id, "warn", "task", f"上下文摘要压缩失败: {e}")

        task_service.cas_update(task_id, ("running",), "success", current_step="done", finished_at=datetime.now())
        await emit("task_status", {"task_id": task_id, "task_status": "success", "current_step": "done"})
        await emit("done", {"task_id": task_id, "finished_at": datetime.now()})
    except asyncio.TimeoutError:
        task_service.cas_update(
            task_id, ("running",), "failed",
            current_step="timeout", finished_at=datetime.now(),
            error_message=f"分析任务超时(>{config_manager.get_int('analysis.task_timeout', 600)}s)",
        )
        await _emit_failure(conversation_id, task_id, "分析任务超时")
    except TaskCancelled:
        task_service.cas_update(task_id, ("queued", "running"), "cancelled", current_step="cancelled", finished_at=datetime.now())
        await emit("task_status", {"task_id": task_id, "task_status": "cancelled", "current_step": "cancelled"})
        await emit("done", {"task_id": task_id, "finished_at": datetime.now()})
    except LLMError as e:
        task_service.cas_update(task_id, ("queued", "running"), "failed", current_step="llm_error", finished_at=datetime.now(), error_message=str(e))
        await _emit_failure(conversation_id, task_id, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("任务执行失败 task_id=%s", task_id)
        message = str(e)[:2000]
        task_service.cas_update(task_id, ("queued", "running"), "failed", current_step="error", finished_at=datetime.now(), error_message=message)
        await _emit_failure(conversation_id, task_id, message)
    finally:
        MessageService(db).touch_last_message_at(conversation_id)
        db.close()
        _cancel_events.pop(task_id, None)


async def _emit_failure(conversation_id: int, task_id: int, message: str) -> None:
    await ws_manager.broadcast(conversation_id, {"type": "error", "task_id": task_id, "error_message": message})
    await ws_manager.broadcast(
        conversation_id, {"type": "task_status", "task_id": task_id, "task_status": "failed", "current_step": "error"}
    )
    await ws_manager.broadcast(conversation_id, {"type": "done", "task_id": task_id, "finished_at": datetime.now()})
