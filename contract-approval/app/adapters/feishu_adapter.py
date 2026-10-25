"""飞书审批适配器骨架(预留)。

切换方式:config/settings.yaml 中 approval.adapter 置为 feishu,并配置 app_id/app_secret。
各方法 docstring 标注了对应的飞书审批 v3 API 映射,接入时按映射实现即可,
业务层(工具/服务)无需任何改动。
"""
from app.adapters.base import (
    ApprovalAdapter,
    ApprovalDetailDTO,
    ApprovalSummaryDTO,
    AttachmentFileDTO,
)


class FeishuApprovalAdapter(ApprovalAdapter):
    """飞书审批适配器(未实现,预留接口)。"""

    def __init__(self, feishu_config: dict):
        self.app_id = feishu_config.get("app_id", "")
        self.app_secret = feishu_config.get("app_secret", "")
        self._tenant_access_token: str | None = None

    def _ensure_token(self) -> str:
        """飞书: POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"""
        raise NotImplementedError("飞书适配器待接入")

    def fetch_pending_approvals(self, limit: int = 50) -> list[ApprovalSummaryDTO]:
        """飞书: POST /approval/v3/instances/query(查询用户待审批实例)"""
        raise NotImplementedError("飞书适配器待接入")

    def get_approval_detail(self, instance_id: str) -> ApprovalDetailDTO:
        """飞书: GET /approval/v3/instances/{instance_id}"""
        raise NotImplementedError("飞书适配器待接入")

    def download_attachment(self, instance_id: str, attachment_id: str) -> AttachmentFileDTO:
        """飞书: GET /approval/v3/files/{file_token}(需要下载凭证与 user_id 参数)"""
        raise NotImplementedError("飞书适配器待接入")

    def write_comment(self, instance_id: str, content: str) -> str:
        """飞书: POST /approval/v3/instances/{instance_id}/comments"""
        raise NotImplementedError("飞书适配器待接入")
