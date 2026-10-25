"""任务服务: 创建(单任务锁)、CAS 状态流转、取消、日志。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisTask, TaskLog

RUNNING_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("success", "failed", "cancelled")


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, conversation_id: int, user_id: int, input_text: str) -> AnalysisTask | None:
        """同一会话同一时间只允许一个运行中任务;冲突时返回 None。"""
        running = self.db.scalar(
            select(AnalysisTask).where(
                AnalysisTask.conversation_id == conversation_id,
                AnalysisTask.task_status.in_(RUNNING_STATUSES),
            )
        )
        if running is not None:
            return None
        task = AnalysisTask(
            conversation_id=conversation_id,
            user_id=user_id,
            input_text=input_text,
            task_status="queued",
            current_step="pending",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: int) -> AnalysisTask | None:
        return self.db.get(AnalysisTask, task_id)

    def cas_update(self, task_id: int, from_statuses: tuple[str, ...], to_status: str, **fields) -> bool:
        """乐观锁状态流转: 仅当当前状态在 from_statuses 中才更新,防止并发覆盖终态。"""
        task = self.db.get(AnalysisTask, task_id)
        if task is None or task.task_status not in from_statuses:
            return False
        task.task_status = to_status
        for k, v in fields.items():
            setattr(task, k, v)
        self.db.commit()
        return True

    def log(self, task_id: int | None, level: str, log_type: str, content: str) -> None:
        self.db.add(
            TaskLog(task_id=task_id, log_level=level, log_type=log_type, log_content=content[:4000])
        )
        self.db.commit()

    def recover_interrupted(self) -> int:
        """服务重启后,将遗留的 queued/running 任务标记为 failed。"""
        tasks = (
            self.db.scalars(
                select(AnalysisTask).where(AnalysisTask.task_status.in_(RUNNING_STATUSES))
            )
            .all()
        )
        for t in tasks:
            t.task_status = "failed"
            t.error_message = "服务重启,任务中断"
            t.finished_at = datetime.now()
            t.current_step = "recovered"
        self.db.commit()
        return len(tasks)
