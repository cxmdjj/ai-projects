"""审批系统适配器抽象基类与数据对象。"""
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalSummaryDTO(BaseModel):
    instance_id: str
    title: str = ""
    applicant: str = ""
    apply_time: datetime | None = None
    attachment_count: int = 0


class AttachmentMetaDTO(BaseModel):
    attachment_id: str
    file_name: str = ""
    file_type: str = ""
    size: int = 0


class ApprovalDetailDTO(BaseModel):
    instance_id: str
    title: str = ""
    applicant: str = ""
    apply_time: datetime | None = None
    form_data: dict = Field(default_factory=dict)
    attachments: list[AttachmentMetaDTO] = Field(default_factory=list)


class AttachmentFileDTO(BaseModel):
    file_name: str
    file_type: str
    content: bytes
    # 可选:审批系统侧存储的预识别文本路径(扫描件演示降级 OCR 用)
    ocr_text_path: str | None = None


class ApprovalAdapter(ABC):
    """审批系统接口抽象:mock 与 feishu 实现可配置切换,业务代码零改动。"""

    @abstractmethod
    def fetch_pending_approvals(self, limit: int = 50) -> list[ApprovalSummaryDTO]:
        """拉取待处理审批单列表。"""

    @abstractmethod
    def get_approval_detail(self, instance_id: str) -> ApprovalDetailDTO:
        """查询单个审批单详情(审批信息、表单数据、附件信息)。"""

    @abstractmethod
    def download_attachment(self, instance_id: str, attachment_id: str) -> AttachmentFileDTO:
        """下载附件,返回文件名、类型与字节内容。"""

    @abstractmethod
    def write_comment(self, instance_id: str, content: str) -> str:
        """将评论写回审批单评论区,返回审批系统响应文本。"""
