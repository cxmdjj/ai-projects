"""适配器工厂:按配置返回单例。"""
from app.adapters.base import ApprovalAdapter
from app.config import settings

_instance: ApprovalAdapter | None = None


def get_approval_adapter() -> ApprovalAdapter:
    global _instance
    if _instance is None:
        kind = settings["approval"]["adapter"]
        if kind == "mock":
            from app.adapters.mock_adapter import MockApprovalAdapter

            fail = set(settings["approval"].get("mock", {}).get("fail_write_for") or [])
            _instance = MockApprovalAdapter(fail_write_for=fail)
        elif kind == "feishu":
            from app.adapters.feishu_adapter import FeishuApprovalAdapter

            _instance = FeishuApprovalAdapter(settings["approval"].get("feishu", {}))
        else:
            raise ValueError(f"未知审批适配器: {kind},可选 mock | feishu")
    return _instance


def reset_adapter() -> None:
    """测试/演示用:重置单例。"""
    global _instance
    _instance = None
