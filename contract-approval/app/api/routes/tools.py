"""工具服务 REST 端点:7 个工具各一个 POST,请求体即工具参数。"""
from fastapi import APIRouter, Body

from app.tools.approval_tools import (
    download_contract_attachment,
    get_contract_approval,
    list_pending_contract_approvals,
)
from app.tools.output_tools import save_review_result, write_approval_comment
from app.tools.parse_tools import parse_contract_document
from app.tools.review_tools import run_contract_rules

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/list_pending_contract_approvals")
def api_list_pending(payload: dict = Body(default={})):
    return list_pending_contract_approvals(payload.get("limit", 50))


@router.post("/get_contract_approval")
def api_get_approval(payload: dict = Body(default={})):
    return get_contract_approval(payload.get("instance_id", ""))


@router.post("/download_contract_attachment")
def api_download(payload: dict = Body(default={})):
    return download_contract_attachment(
        payload.get("instance_id", ""), payload.get("attachment_id", ""), payload.get("file_name", "")
    )


@router.post("/parse_contract_document")
def api_parse(payload: dict = Body(default={})):
    return parse_contract_document(payload.get("document_id", 0))


@router.post("/run_contract_rules")
def api_run_rules(payload: dict = Body(default={})):
    return run_contract_rules(payload.get("case_id", 0))


@router.post("/save_review_result")
def api_save_result(payload: dict = Body(default={})):
    return save_review_result(
        payload.get("case_id", 0),
        payload.get("overall_risk_level", ""),
        payload.get("summary_text", ""),
        payload.get("focus_points_json", ""),
        payload.get("comment_text", ""),
    )


@router.post("/write_approval_comment")
def api_write_comment(payload: dict = Body(default={})):
    return write_approval_comment(payload.get("instance_id", ""), payload.get("review_id", 0))
