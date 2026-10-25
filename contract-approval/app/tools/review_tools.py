"""工具5:run_contract_rules —— 执行规则审查并返回命中结果和风险结论。"""
from app.db import SessionLocal
from app.enums import LogType, ParseStatus, TaskStatus
from app.models import ApprovalTask, ContractParse
from app.schemas.common import ToolResult
from app.services import log_service, rule_service, state
from app.utils.errors import RuleEngineError, StateTransitionError


def run_contract_rules(case_id: int) -> dict:
    """对任务(case_id = approval_tasks.id)执行规则审查。

    产出:总风险等级、命中规则列表(证据+位置+建议)、中文摘要、审批关注点、回写文本。
    """
    with SessionLocal() as db:
        task = db.get(ApprovalTask, case_id)
        if task is None:
            return ToolResult(success=False, error=f"任务不存在: {case_id}").model_dump()
        try:
            state.transition(db, task, TaskStatus.REVIEWING.value)
            parse = (
                db.query(ContractParse)
                .filter_by(task_id=task.id, parse_status=ParseStatus.SUCCESS.value)
                .first()
            )
            if parse is None:
                raise RuleEngineError("无可用解析结果,请先执行解析")
            output = rule_service.run(db, task, parse)
            log_service.log_info(
                db, task.id, LogType.REVIEW.value,
                f"规则审查完成:命中 {len(output['hits'])} 项,总风险等级 {output['overall_risk_level']}",
            )
            db.commit()
            return ToolResult(success=True, data=output).model_dump()
        except StateTransitionError as e:
            db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
        except Exception as e:
            db.rollback()
            try:
                t = db.get(ApprovalTask, case_id)
                state.block(db, t, f"规则审查失败: {e}")
                log_service.log_error(db, case_id, LogType.REVIEW.value, str(e))
                db.commit()
            except Exception:
                db.rollback()
            return ToolResult(success=False, error=str(e)).model_dump()
