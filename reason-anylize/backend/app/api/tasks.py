"""任务接口: /api/tasks/{task_id}(状态查询、事件回放、取消)。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import BizError
from app.database import get_db
from app.deps import get_current_user
from app.models import AnalysisTask, User
from app.services.ws_manager import ws_manager
from app.workers import task_worker

router = APIRouter(prefix="/api/tasks")


def _task_view(task: AnalysisTask) -> dict:
    return {
        "task_id": task.id,
        "conversation_id": task.conversation_id,
        "task_status": task.task_status,
        "current_step": task.current_step,
        "input_text": task.input_text,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "error_message": task.error_message,
    }


def _get_owned_task(task_id: int, user: User, db: Session) -> AnalysisTask:
    task = db.get(AnalysisTask, task_id)
    if task is None or task.user_id != user.id:
        raise BizError("任务不存在或无权访问", 404)
    return task


@router.get("/{task_id}")
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _task_view(_get_owned_task(task_id, user, db))


@router.get("/{task_id}/events")
def get_task_events(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """断线重连后回放任务事件缓冲(最多 200 条)。"""
    from fastapi.encoders import jsonable_encoder

    _get_owned_task(task_id, user, db)
    return {"events": jsonable_encoder(ws_manager.get_events(task_id))}


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_owned_task(task_id, user, db)
    if task.task_status in ("queued", "running"):
        task_worker.cancel(task_id)
        return {"task_id": task_id, "requested": True}
    return {"task_id": task_id, "requested": False, "message": "任务已处于终态,无需取消"}
