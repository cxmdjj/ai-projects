"""回写模块:评论回写审批评论区 + 回写日志时间线。"""
from app.enums import LogType, WriteStatus
from app.models import CommentLog
from app.services import log_service, state


def write_comment(db, task, review, adapter) -> tuple[bool, str]:
    """执行一次回写:writing → 适配器 → success/failed,每次尝试追加 comment_logs 两条。"""
    state.set_write_status(db, task, WriteStatus.WRITING.value)
    db.add(CommentLog(task_id=task.id, write_status=WriteStatus.WRITING.value,
                      write_response_text="开始回写审批评论区"))
    db.flush()
    try:
        resp = adapter.write_comment(task.approval_code, review.comment_text)
    except Exception as e:
        state.set_write_status(db, task, WriteStatus.FAILED.value)
        db.add(CommentLog(task_id=task.id, write_status=WriteStatus.FAILED.value, write_response_text=str(e)))
        log_service.log_error(db, task.id, LogType.WRITE_BACK.value, f"评论回写失败: {e}")
        return False, str(e)
    state.set_write_status(db, task, WriteStatus.SUCCESS.value)
    db.add(CommentLog(task_id=task.id, write_status=WriteStatus.SUCCESS.value, write_response_text=resp))
    log_service.log_info(db, task.id, LogType.WRITE_BACK.value, f"评论回写成功: {resp}")
    return True, resp
