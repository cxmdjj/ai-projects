from types import SimpleNamespace

import pytest

from app.enums import TaskStatus, WriteStatus
from app.services.state import ALLOWED_TRANSITIONS, retry, set_write_status, transition
from app.utils.errors import StateTransitionError


@pytest.fixture(autouse=True)
def fake_log_service(monkeypatch):
    """替身日志模块:状态机测试不落库。"""
    fake = SimpleNamespace(log=lambda *a, **k: None)
    monkeypatch.setattr("app.services.state.log_service", fake)
    return fake


def _task(status=TaskStatus.PENDING.value, write=WriteStatus.NOT_WRITTEN.value):
    return SimpleNamespace(task_status=status, write_status=write, block_reason=None, id=1)


def _db():
    return SimpleNamespace()


def test_allowed_transitions():
    assert TaskStatus.PARSING.value in ALLOWED_TRANSITIONS[TaskStatus.PENDING.value]
    assert TaskStatus.BLOCKED.value in ALLOWED_TRANSITIONS[TaskStatus.PENDING.value]  # 附件缺失等直接阻塞
    assert TaskStatus.BLOCKED.value in ALLOWED_TRANSITIONS[TaskStatus.REVIEWING.value]
    assert ALLOWED_TRANSITIONS[TaskStatus.DONE.value] == set()  # 终态


def test_legal_transition():
    t = _task(TaskStatus.PENDING.value)
    transition(_db(), t, TaskStatus.PARSING.value)
    assert t.task_status == TaskStatus.PARSING.value


def test_illegal_transition_raises():
    t = _task(TaskStatus.DONE.value)
    with pytest.raises(StateTransitionError):
        transition(_db(), t, TaskStatus.PARSING.value)


def test_transition_idempotent():
    t = _task(TaskStatus.PARSING.value)
    transition(_db(), t, TaskStatus.PARSING.value)  # 不抛异常
    assert t.task_status == TaskStatus.PARSING.value


def test_block_sets_reason():
    t = _task(TaskStatus.PENDING.value)
    from app.services.state import block
    block(_db(), t, "附件缺失")
    assert t.task_status == TaskStatus.BLOCKED.value
    assert t.block_reason == "附件缺失"


def test_retry_only_from_blocked():
    t = _task(TaskStatus.BLOCKED.value)
    retry(_db(), t, TaskStatus.PARSING.value)
    assert t.task_status == TaskStatus.PARSING.value
    t2 = _task(TaskStatus.PENDING.value)
    with pytest.raises(StateTransitionError):
        retry(_db(), t2, TaskStatus.PARSING.value)
    t3 = _task(TaskStatus.BLOCKED.value)
    with pytest.raises(StateTransitionError):
        retry(_db(), t3, TaskStatus.DONE.value)  # 目标阶段非法


def test_write_status_flow():
    t = _task(TaskStatus.DONE.value, WriteStatus.NOT_WRITTEN.value)
    set_write_status(_db(), t, WriteStatus.WRITING.value)
    set_write_status(_db(), t, WriteStatus.FAILED.value)
    set_write_status(_db(), t, WriteStatus.WRITING.value)  # failed 可重试
    set_write_status(_db(), t, WriteStatus.SUCCESS.value)
    with pytest.raises(StateTransitionError):
        set_write_status(_db(), t, WriteStatus.WRITING.value)  # success 终态
