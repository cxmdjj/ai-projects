"""全部枚举定义。DB 中以字符串存储。"""
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"
    DONE = "done"


class WriteStatus(str, Enum):
    NOT_WRITTEN = "not_written"
    WRITING = "writing"
    SUCCESS = "success"
    FAILED = "failed"


class ParseStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EMPTY = "empty"


class DownloadStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RuleStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ExtractStatus(str, Enum):
    EXTRACTED = "extracted"
    MISSING = "missing"


class LogLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class LogType(str, Enum):
    PULL = "pull"
    DOWNLOAD = "download"
    PARSE = "parse"
    OCR = "ocr"
    REVIEW = "review"
    SAVE = "save"
    WRITE_BACK = "write_back"
    RETRY = "retry"
    STATE = "state"


# 风险等级中英文映射(输出格式要求:低、中、高)
RISK_LEVEL_ZH = {
    RiskLevel.LOW.value: "低",
    RiskLevel.MEDIUM.value: "中",
    RiskLevel.HIGH.value: "高",
}
RISK_ZH_TO_EN = {v: k for k, v in RISK_LEVEL_ZH.items()}

# 状态中文名
TASK_STATUS_ZH = {
    TaskStatus.PENDING.value: "待处理",
    TaskStatus.PARSING.value: "解析中",
    TaskStatus.REVIEWING.value: "审查中",
    TaskStatus.BLOCKED.value: "已阻塞",
    TaskStatus.DONE.value: "已完成",
}
WRITE_STATUS_ZH = {
    WriteStatus.NOT_WRITTEN.value: "未回写",
    WriteStatus.WRITING.value: "回写中",
    WriteStatus.SUCCESS.value: "回写成功",
    WriteStatus.FAILED.value: "回写失败",
}
