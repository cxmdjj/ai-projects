"""业务异常体系。工具层统一捕获,不向调用端抛裸异常。"""


class ContractApprovalError(Exception):
    """业务异常基类"""


class ApprovalApiError(ContractApprovalError):
    """审批系统接口调用失败"""


class AttachmentMissingError(ContractApprovalError):
    """附件缺失"""


class DownloadError(ContractApprovalError):
    """附件下载失败"""


class OcrUnavailableError(ContractApprovalError):
    """图片无法识别(OCR 引擎不可用或识别结果为空)"""


class EmptyDocumentError(ContractApprovalError):
    """文档内容为空"""


class ParseError(ContractApprovalError):
    """文档解析异常"""


class RuleEngineError(ContractApprovalError):
    """规则引擎异常"""


class StateTransitionError(ContractApprovalError):
    """非法状态流转"""


class NotFoundError(ContractApprovalError):
    """任务/附件/审查结果不存在"""
