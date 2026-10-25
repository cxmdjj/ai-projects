"""结果接口: /api/results/{task_id}(六部分结果、导出、下载)。"""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import paths
from app.core.exceptions import BizError, PathTraversalError
from app.database import get_db
from app.deps import get_current_user
from app.models import AnalysisTask, User
from app.services.result_service import ResultService

router = APIRouter(prefix="/api/results")


def _get_owned_task(task_id: int, user: User, db: Session) -> AnalysisTask:
    task = db.get(AnalysisTask, task_id)
    if task is None or task.user_id != user.id:
        raise BizError("任务不存在或无权访问", 404)
    return task


@router.get("/{task_id}")
def get_result(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_task(task_id, user, db)
    result = ResultService(db).get_by_task(task_id)
    if result is None:
        raise BizError("该任务尚未生成分析结果", 404)
    return ResultService.to_dict(result)


@router.get("/{task_id}/export")
def export_result(task_id: int, format: str = "md", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned_task(task_id, user, db)
    result = ResultService(db).get_by_task(task_id)
    if result is None:
        raise BizError("该任务尚未生成分析结果", 404)
    content, media_type = ResultService(db).export(result, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="task_{task_id}_result.{format}"',
        },
    )


@router.get("/{task_id}/download")
def download(task_id: int, file: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """下载结果文件: 不带 file 参数下载系统生成的分析报告,带 file 下载 result_file 工具生成的文件。"""
    task = _get_owned_task(task_id, user, db)
    exports = paths.exports_dir(user.id, task.conversation_id)
    if file:
        try:
            target = paths.safe_join(exports, file)
        except PathTraversalError:
            raise BizError("非法文件名", 400)
        if not target.exists() or not target.is_file():
            raise BizError("结果文件不存在", 404)
        return FileResponse(target, filename=target.name)
    result = ResultService(db).get_by_task(task_id)
    if result is None or not result.result_file_path:
        raise BizError("该任务尚未生成结果文件", 404)
    target = paths.STORAGE_ROOT / result.result_file_path
    if not target.exists():
        raise BizError("结果文件已丢失", 404)
    return FileResponse(target, filename=target.name)
