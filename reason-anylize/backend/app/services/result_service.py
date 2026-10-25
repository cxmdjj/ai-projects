"""结果服务: 六部分结构化结果落库、结果文件生成与导出。"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import paths
from app.core.exceptions import BizError
from app.engine.result_writer import render_html, render_markdown
from app.models import AnalysisResult, AnalysisTask


class ResultService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, task: AnalysisTask, payload: dict) -> AnalysisResult:
        key_metrics = json.dumps(payload.get("key_metrics", []), ensure_ascii=False)
        evidence_list = json.dumps(payload.get("evidence_list", []), ensure_ascii=False)
        next_actions = json.dumps(payload.get("next_action_text", []), ensure_ascii=False)
        markdown = render_markdown(payload)

        exports = paths.exports_dir(task.user_id, task.conversation_id)
        exports.mkdir(parents=True, exist_ok=True)
        md_name = f"{task.id}_analysis_result.md"
        md_path = exports / md_name
        md_path.write_text(markdown, encoding="utf-8")
        html_path = exports / f"{task.id}_analysis_result.html"
        html_path.write_text(render_html(payload, markdown), encoding="utf-8")

        result = AnalysisResult(
            task_id=task.id,
            conversation_id=task.conversation_id,
            problem_definition=payload["problem_definition"],
            key_metrics_json=key_metrics,
            evidence_list_json=evidence_list,
            conclusion_text=payload["conclusion_text"],
            missing_data_text=payload["missing_data_text"],
            next_action_text=next_actions,
            result_markdown=markdown,
            result_file_path=str(md_path.relative_to(paths.STORAGE_ROOT)).replace("\\", "/"),
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_by_task(self, task_id: int) -> AnalysisResult | None:
        return self.db.scalar(
            select(AnalysisResult).where(AnalysisResult.task_id == task_id).order_by(AnalysisResult.id.desc())
        )

    @staticmethod
    def to_dict(result: AnalysisResult) -> dict:
        return {
            "result_id": result.id,
            "task_id": result.task_id,
            "problem_definition": result.problem_definition,
            "key_metrics": json.loads(result.key_metrics_json or "[]"),
            "evidence_list": json.loads(result.evidence_list_json or "[]"),
            "conclusion_text": result.conclusion_text,
            "missing_data_text": result.missing_data_text,
            "next_action_text": json.loads(result.next_action_text or "[]"),
            "result_markdown": result.result_markdown,
            "result_file_path": result.result_file_path,
            "created_at": result.created_at,
        }

    @staticmethod
    def to_compact(result: AnalysisResult) -> dict:
        """注入下一轮上下文的精简版本。"""
        d = ResultService.to_dict(result)
        return {
            "problem_definition": d["problem_definition"],
            "key_metrics": d["key_metrics"],
            "conclusion_text": d["conclusion_text"],
            "missing_data_text": d["missing_data_text"],
            "next_action_text": d["next_action_text"][:3],
        }

    def export(self, result: AnalysisResult, fmt: str) -> tuple[str, str]:
        """返回 (content, media_type)。"""
        if fmt == "md":
            return result.result_markdown, "text/markdown; charset=utf-8"
        if fmt == "html":
            return render_html(ResultService.to_dict(result), result.result_markdown), "text/html; charset=utf-8"
        if fmt == "json":
            return json.dumps(ResultService.to_dict(result), ensure_ascii=False, indent=2, default=str), "application/json"
        raise BizError("不支持的导出格式,支持 md / html / json", 400)
