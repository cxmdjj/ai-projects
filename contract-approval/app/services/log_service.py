"""日志模块:全链路 task_logs 写入。"""
from app.enums import LogLevel
from app.models import TaskLog


def log(db, task_id: int | None, level: str, log_type: str, content: str) -> TaskLog:
    entry = TaskLog(task_id=task_id, log_level=level, log_type=log_type, log_content=content)
    db.add(entry)
    return entry


def log_info(db, task_id: int | None, log_type: str, content: str) -> TaskLog:
    return log(db, task_id, LogLevel.INFO.value, log_type, content)


def log_warn(db, task_id: int | None, log_type: str, content: str) -> TaskLog:
    return log(db, task_id, LogLevel.WARN.value, log_type, content)


def log_error(db, task_id: int | None, log_type: str, content: str) -> TaskLog:
    return log(db, task_id, LogLevel.ERROR.value, log_type, content)
