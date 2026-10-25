"""状态机:任务状态与回写状态的流转校验、阻塞、人工重试。"""
from app.enums import LogLevel, LogType, TaskStatus, WriteStatus
from app.services import log_service
from app.utils.errors import StateTransitionError

ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING.value: {TaskStatus.PARSING.value, TaskStatus.BLOCKED.value},
    TaskStatus.PARSING.value: {TaskStatus.REVIEWING.value, TaskStatus.BLOCKED.value},
    TaskStatus.REVIEWING.value: {TaskStatus.DONE.value, TaskStatus.BLOCKED.value},
    TaskStatus.BLOCKED.value: {TaskStatus.PARSING.value, TaskStatus.REVIEWING.value},
    TaskStatus.DONE.value: set(),
}

WRITE_TRANSITIONS = {
    WriteStatus.NOT_WRITTEN.value: {WriteStatus.WRITING.value},
    WriteStatus.WRITING.value: {WriteStatus.SUCCESS.value, WriteStatus.FAILED.value},
    WriteStatus.FAILED.value: {WriteStatus.WRITING.value},
    WriteStatus.SUCCESS.value: set(),
}


def transition(db, task, new_status: str, reason: str | None = None) -> None:
    """任务状态流转。同状态为幂等空操作,非法流转抛 StateTransitionError。"""
    if task.task_status == new_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(task.task_status, set())
    if new_status not in allowed:
        raise StateTransitionError(f"非法状态流转: {task.task_status} → {new_status}")
    old = task.task_status
    task.task_status = new_status
    if new_status == TaskStatus.BLOCKED.value:
        task.block_reason = reason
    log_service.log(
        db,
        task.id,
        LogLevel.INFO.value,
        LogType.STATE.value,
        f"状态流转: {old} → {new_status}" + (f",原因: {reason}" if reason else ""),
    )


def block(db, task, reason: str) -> None:
    """进入阻塞状态(记录 block_reason + 状态日志)。"""
    transition(db, task, TaskStatus.BLOCKED.value, reason=reason)
    log_service.log(db, task.id, LogLevel.ERROR.value, LogType.STATE.value, f"任务阻塞: {reason}")


def retry(db, task, target_stage: str) -> None:
    """人工重试:blocked → parsing 或 reviewing。"""
    if task.task_status != TaskStatus.BLOCKED.value:
        raise StateTransitionError(f"仅 blocked 任务可重试,当前状态: {task.task_status}")
    if target_stage not in (TaskStatus.PARSING.value, TaskStatus.REVIEWING.value):
        raise StateTransitionError(f"重试目标阶段非法: {target_stage},可选 parsing | reviewing")
    task.task_status = target_stage
    log_service.log(db, task.id, LogLevel.INFO.value, LogType.RETRY.value, f"人工重试: blocked → {target_stage}")


def set_write_status(db, task, new_status: str) -> None:
    """回写状态流转。同状态为幂等空操作,非法流转抛 StateTransitionError。"""
    if task.write_status == new_status:
        return
    allowed = WRITE_TRANSITIONS.get(task.write_status, set())
    if new_status not in allowed:
        raise StateTransitionError(f"非法回写状态流转: {task.write_status} → {new_status}")
    task.write_status = new_status
