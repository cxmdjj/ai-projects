"""CLI 一键闭环演示:待办拉取 → 附件下载 → 文档解析 → 规则审查 → 结果入库 → 评论回写。

覆盖场景:
  1. HT-2026-001 文本 PDF 全链路(总风险 中)
  2. HT-2026-002 扫描件 JPG 全链路(降级 OCR,大写金额,总风险 高)
  3. HT-2026-003 附件缺失 → blocked → 模拟补传附件 → 人工重试 → done(总风险 低)
  4. HT-2026-004 文档内容为空 → blocked
  5. --fail-write 回写失败 → 修复 → 重试成功
  6. 重复拉取去重验证(无新建、状态不重置)

用法:
  uv run python -m scripts.demo_closed_loop                      # 默认全场景
  uv run python -m scripts.demo_closed_loop --only HT-2026-001   # 仅演示指定审批单全链路
  uv run python -m scripts.demo_closed_loop --fail-write HT-2026-001   # 追加回写失败重试演示
  uv run python -m scripts.demo_closed_loop --list-only          # 仅拉取待办
  uv run python -m scripts.demo_closed_loop --strict             # 验收模式:存在 blocked/failed 退出码为 1
"""
import argparse
import json
import sys

from app.db import SessionLocal
from app.enums import TaskStatus, WriteStatus
from app.models import ApprovalTask, CommentLog, ReviewResult
from app.tools.approval_tools import (
    download_contract_attachment,
    get_contract_approval,
    list_pending_contract_approvals,
)
from app.tools.output_tools import save_review_result, write_approval_comment
from app.tools.parse_tools import parse_contract_document
from app.tools.review_tools import run_contract_rules


def step(title: str) -> None:
    print(f"\n{'=' * 64}\n▶ {title}\n{'=' * 64}")


def check(result: dict, action: str) -> dict | None:
    if not result.get("success"):
        print(f"  ✗ {action}失败: {result.get('error')}")
    return result.get("data") if result.get("success") else None


def run_full_chain(instance_id: str) -> None:
    """单个审批单:详情 → 下载 → 解析 → 审查 → 保存 → 回写。"""
    step(f"审批单 {instance_id} 全链路")
    d = get_contract_approval(instance_id)
    if not d["success"]:
        print(f"  ✗ 详情获取失败: {d['error']}")
        return
    attachments = d["data"]["attachments"]
    print(f"  标题: {d['data']['approval']['title']} | 申请人: {d['data']['approval']['applicant']}")
    if not attachments:
        print(f"  ⚠ 审批单无附件 → 尝试下载将触发 blocked(附件缺失)")
        return
    att = attachments[0]
    dl = download_contract_attachment(instance_id, att["attachment_id"], att["file_name"])
    if not dl["success"]:
        print(f"  ✗ 下载失败(任务应已 blocked): {dl['error']}")
        return
    print(f"  ✓ 附件下载: {dl['data']['local_path']}")
    print(f"    md5={dl['data']['md5']}  大小={dl['data']['size']} 字节")

    p = parse_contract_document(dl["data"]["attachment_record_id"])
    if not p["success"]:
        print(f"  ✗ 解析失败(任务应已 blocked): {p['error']}")
        return
    print(f"  ✓ 解析成功: {p['data']['engine']}")
    for f in p["data"]["basic_info"]:
        mark = "✓" if f["status"] == "extracted" else "✗"
        print(f"    {mark} {f['label']}: {f['value'] or '未提取到'}")

    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code=instance_id).first()
        case_id = task.id
    rv = run_contract_rules(case_id)
    if not rv["success"]:
        print(f"  ✗ 规则审查失败: {rv['error']}")
        return
    print(f"  ✓ 规则审查: 总风险等级 【{rv['data']['overall_risk_level']}】 命中 {len(rv['data']['hits'])} 项")
    for h in rv["data"]["hits"]:
        pos = f" @ {h['evidence_position']}" if h["evidence_position"] else ""
        print(f"      [{h['risk_level']:6}] {h['rule_code']} {h['rule_name']}{pos}")

    sv = save_review_result(case_id, rv["data"]["overall_risk_level"], rv["data"]["summary_text"],
                            json.dumps(rv["data"]["focus_points"], ensure_ascii=False), rv["data"]["comment_text"])
    if not sv["success"]:
        print(f"  ✗ 保存失败: {sv['error']}")
        return
    print(f"  ✓ 结果保存 (review_id={sv['data']['review_id']}),任务状态 → {sv['data']['task_status']}")

    w = write_approval_comment(instance_id, sv["data"]["review_id"])
    if w["success"]:
        print(f"  ✓ 评论回写: {w['data']['write_status']} | {w['data']['response']}")
    else:
        print(f"  ✗ 评论回写: {w['data']['write_status']} | {w['error']}")
    print("\n  ----- 回写评论内容 -----")
    print(rv["data"]["comment_text"])
    print("  ------------------------")


def demo_blocked_missing_attachment() -> None:
    """HT-2026-003:附件缺失 blocked → 补传 → 重试 → 恢复。"""
    step("blocked 演示①: HT-2026-003 附件缺失 → 人工重试恢复")
    print("  1) 尝试下载不存在的附件…")
    dl = download_contract_attachment("HT-2026-003", "ATT-2026-003-1", "办公家具采购合同.pdf")
    print(f"     ✗ 下载失败: {dl['error']}(任务已进入 blocked)")

    with SessionLocal() as db:
        task = db.query(ApprovalTask).filter_by(approval_code="HT-2026-003").first()
        print(f"  2) 当前任务状态: {task.task_status} | 阻塞原因: {task.block_reason}")
        # 模拟审批人在原系统补传附件
        from app.adapters.factory import get_approval_adapter
        adapter = get_approval_adapter()
        adapter.add_attachment("HT-2026-003", "ATT-2026-003-1", "办公家具采购合同.pdf", "pdf",
                               "samples/contracts/office_furniture_contract.pdf")
        print("  3) 模拟审批人补传附件完成")
        from app.services import state
        state.retry(db, task, TaskStatus.PARSING.value)
        db.commit()
        print(f"  4) 人工重试 → 任务状态: {task.task_status}")
    run_full_chain("HT-2026-003")


def demo_blocked_empty_document() -> None:
    """HT-2026-004:文档内容为空 → blocked。"""
    step("blocked 演示②: HT-2026-004 文档内容为空")
    d = get_contract_approval("HT-2026-004")
    att = d["data"]["attachments"][0]
    dl = download_contract_attachment("HT-2026-004", att["attachment_id"], att["file_name"])
    print(f"  ✓ 附件下载成功(文件本身正常)")
    p = parse_contract_document(dl["data"]["attachment_record_id"])
    print(f"  ✗ 解析失败: {p['error']}(任务已进入 blocked,演示保留 blocked 状态)")


def demo_write_recovery(fail_codes: list[str]) -> None:
    """故障已注入且第一次回写已失败:移除注入后重试,演示恢复。"""
    step(f"回写失败重试演示: {fail_codes} 故障恢复后重新回写")
    from app.adapters.factory import get_approval_adapter
    adapter = get_approval_adapter()
    adapter.fail_write_for.difference_update(fail_codes)
    for code in fail_codes:
        with SessionLocal() as db:
            task = db.query(ApprovalTask).filter_by(approval_code=code).first()
            review = db.query(ReviewResult).filter_by(task_id=task.id).first()
            if not review:
                print(f"  {code} 无审查结果,跳过")
                continue
            w = write_approval_comment(code, review.id)
            print(f"  {code} 重新回写: success={w['success']} | write_status={w['data']['write_status']}")
            logs = db.query(CommentLog).filter_by(task_id=task.id).order_by(CommentLog.id).all()
            for l in logs:
                print(f"    comment_logs: [{l.write_status}] {l.write_response_text}")


def print_summary() -> None:
    with SessionLocal() as db:
        tasks = db.query(ApprovalTask).order_by(ApprovalTask.id).all()
        print("\n汇总表:")
        print(f"  {'审批编号':<14}{'任务状态':<10}{'总风险':<8}{'回写状态':<10}阻塞原因")
        for t in tasks:
            review = db.query(ReviewResult).filter_by(task_id=t.id).first()
            risk = review.overall_risk_level if review else "-"
            reason = f" | {t.block_reason}" if t.block_reason else ""
            print(f"  {t.approval_code:<14}{t.task_status:<10}{risk:<8}{t.write_status:<10}{reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="合同审批自动审查系统闭环演示")
    parser.add_argument("--only", help="仅演示指定审批单(如 HT-2026-001)")
    parser.add_argument("--list-only", action="store_true", help="仅拉取待办列表")
    parser.add_argument("--fail-write", nargs="*", default=[], help="追加回写失败重试演示的审批单")
    parser.add_argument("--strict", action="store_true", help="验收模式:存在 blocked/failed 时退出码 1")
    parser.add_argument("--fresh", action="store_true", help="清空数据库与附件目录后重新演示(重复运行演示用)")
    args = parser.parse_args()

    if args.fresh:
        import shutil

        from app.config import PROJECT_ROOT
        from app.db import Base, engine

        db_file = PROJECT_ROOT / "data" / "contract_approval.db"
        deleted = False
        if db_file.exists():
            try:
                db_file.unlink()
                deleted = True
                for extra in (PROJECT_ROOT / "data").glob("contract_approval.db-*"):
                    extra.unlink(missing_ok=True)
            except OSError:
                deleted = False
        shutil.rmtree(PROJECT_ROOT / "data" / "attachments", ignore_errors=True)
        if deleted:
            print("  已清空数据库与附件目录,开始全新演示")
        else:
            # 数据库文件被占用(如 Web 服务运行中):降级为清空全部数据表
            try:
                Base.metadata.drop_all(engine)
            except Exception as e:
                print(f"  无法清空数据库(Web 服务可能正在运行): {e}")
                sys.exit(2)
            print("  数据库文件被占用,已改为清空全部数据表(Web 服务运行中亦可演示)")

    step("步骤 0:初始化(建表 + 种子规则)")
    from app.db import Base, engine
    Base.metadata.create_all(engine)
    from scripts.seed_rules import seed_rules
    created, updated = seed_rules()
    print(f"  数据表就绪,种子规则: 新建 {created} 条 / 更新 {updated} 条")

    step("步骤 1:工具1 待办拉取(list_pending_contract_approvals)")
    r = list_pending_contract_approvals()
    if not r["success"]:
        print(f"  ✗ 拉取失败: {r['error']}")
        sys.exit(2)
    print(f"  ✓ 拉取 {r['data']['total']} 单,新建 {r['data']['created']} 单,去重更新 {r['data']['updated']} 单")
    for t in r["data"]["tasks"]:
        print(f"    {t['approval_code']}  {t['approval_title']}  申请人:{t['applicant_name']}  附件:{t['attachment_count']}")

    if args.list_only:
        sys.exit(0)

    # 回写故障注入:先注入,让第一次回写失败,链路结束后再演示恢复重试
    if args.fail_write:
        from app.adapters.factory import get_approval_adapter
        adapter = get_approval_adapter()
        adapter.fail_write_for.update(args.fail_write)
        print(f"\n  注:已对 {args.fail_write} 注入回写故障,第一次回写将失败(演示失败重试)")

    if args.only:
        run_full_chain(args.only)
    else:
        run_full_chain("HT-2026-001")
        run_full_chain("HT-2026-002")
        demo_blocked_missing_attachment()
        demo_blocked_empty_document()

    if args.fail_write:
        demo_write_recovery(args.fail_write)

    step("步骤 7:重复拉取验证去重(不新建、不重置状态)")
    r2 = list_pending_contract_approvals()
    print(f"  ✓ 再次拉取: 新建 {r2['data']['created']} 单 / 更新 {r2['data']['updated']} 单(全部为更新即去重生效)")

    print_summary()

    if args.strict:
        with SessionLocal() as db:
            tasks = db.query(ApprovalTask).all()
            bad = [t for t in tasks if t.task_status in (TaskStatus.BLOCKED.value,)
                   or t.write_status in (WriteStatus.FAILED.value,)]
        if bad:
            print(f"\n[strict] 存在 {len(bad)} 个 blocked/failed 任务,退出码 1")
            sys.exit(1)
    print("\n闭环演示完成 ✓")


if __name__ == "__main__":
    main()
