"""Mock 审批服务:内存数据 + 故障注入,用于闭环演示与验收。"""
import time
from datetime import datetime
from pathlib import Path

from app.adapters.base import (
    ApprovalAdapter,
    ApprovalDetailDTO,
    ApprovalSummaryDTO,
    AttachmentFileDTO,
    AttachmentMetaDTO,
)
from app.adapters.mock_data import MOCK_APPROVALS
from app.config import PROJECT_ROOT
from app.utils.errors import ApprovalApiError, AttachmentMissingError


class MockApprovalAdapter(ApprovalAdapter):
    """模拟审批系统:数据在内存中,附件从本地示例文件读取。

    - fail_write_for: 故障注入,对指定审批编号的评论回写抛 ApprovalApiError
    - add_attachment: 模拟审批人在原系统补传附件(blocked 重试演示)
    """

    def __init__(self, fail_write_for: set[str] | None = None):
        self._approvals = [dict(a) for a in MOCK_APPROVALS]
        self.comments: dict[str, str] = {}
        self.fail_write_for = fail_write_for or set()

    # ---- 内部辅助 ----
    def _find(self, instance_id: str) -> dict:
        for a in self._approvals:
            if a["instance_id"] == instance_id:
                return a
        raise ApprovalApiError(f"审批单不存在: {instance_id}")

    @staticmethod
    def _local_path(att: dict) -> Path:
        return PROJECT_ROOT / att["local_file"]

    # ---- ApprovalAdapter 接口 ----
    def fetch_pending_approvals(self, limit: int = 50) -> list[ApprovalSummaryDTO]:
        result = []
        for a in self._approvals[:limit]:
            result.append(
                ApprovalSummaryDTO(
                    instance_id=a["instance_id"],
                    title=a["title"],
                    applicant=a["applicant"],
                    apply_time=datetime.fromisoformat(a["apply_time"]),
                    attachment_count=len(a["attachments"]),
                )
            )
        return result

    def get_approval_detail(self, instance_id: str) -> ApprovalDetailDTO:
        a = self._find(instance_id)
        atts = []
        for att in a["attachments"]:
            local = self._local_path(att)
            size = local.stat().st_size if local.exists() else 0
            atts.append(
                AttachmentMetaDTO(
                    attachment_id=att["attachment_id"],
                    file_name=att["file_name"],
                    file_type=att["file_type"],
                    size=size,
                )
            )
        return ApprovalDetailDTO(
            instance_id=instance_id,
            title=a["title"],
            applicant=a["applicant"],
            apply_time=datetime.fromisoformat(a["apply_time"]),
            form_data=a["form_data"],
            attachments=atts,
        )

    def download_attachment(self, instance_id: str, attachment_id: str) -> AttachmentFileDTO:
        a = self._find(instance_id)
        for att in a["attachments"]:
            if att["attachment_id"] == attachment_id:
                local = self._local_path(att)
                if not local.exists():
                    raise ApprovalApiError(
                        f"示例附件文件不存在: {local},请先运行 python -m scripts.generate_samples"
                    )
                return AttachmentFileDTO(
                    file_name=att["file_name"],
                    file_type=att["file_type"],
                    content=local.read_bytes(),
                    ocr_text_path=str(PROJECT_ROOT / att["ocr_json"]) if att.get("ocr_json") else None,
                )
        raise AttachmentMissingError(f"审批单 {instance_id} 无附件 {attachment_id}(附件缺失)")

    def write_comment(self, instance_id: str, content: str) -> str:
        if instance_id in self.fail_write_for:
            raise ApprovalApiError(f"模拟审批系统异常:评论回写接口调用失败({instance_id})")
        self.comments[instance_id] = content
        return f"评论已写入(模拟审批系统), comment_id=mock_{int(time.time() * 1000)}"

    # ---- 演示辅助 ----
    def add_attachment(
        self, instance_id: str, attachment_id: str, file_name: str, file_type: str, local_file: str
    ) -> None:
        """模拟审批人在原审批系统补传附件。"""
        a = self._find(instance_id)
        a["attachments"].append(
            {
                "attachment_id": attachment_id,
                "file_name": file_name,
                "file_type": file_type,
                "local_file": local_file,
            }
        )

    def get_received_comments(self) -> dict[str, str]:
        """返回 Mock 审批系统收到的评论原文(验收"回写成功"直观可见)。"""
        return dict(self.comments)
