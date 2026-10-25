from app.rules.aggregator import build_focus_points, build_summary, compute_risk_level


def _hit(level):
    return {"rule_code": "R001", "rule_name": "测试规则", "risk_level": level,
            "evidence_text": "证据", "suggestion_text": "建议"}


def test_compute_risk_level():
    assert compute_risk_level([]) == "低"
    assert compute_risk_level([_hit("low")]) == "低"
    assert compute_risk_level([_hit("medium")]) == "中"
    assert compute_risk_level([_hit("medium"), _hit("medium")]) == "中"
    assert compute_risk_level([_hit("medium")] * 3) == "高"   # 中风险积累 ≥3 升级
    assert compute_risk_level([_hit("high")]) == "高"
    assert compute_risk_level([_hit("high"), _hit("low")]) == "高"


def test_build_summary():
    basic = {"contract_no": {"value": "HT-1", "status": "extracted"},
             "amount": {"label": "金额", "status": "missing"}}
    s = build_summary(basic, [_hit("high")], "高")
    assert "HT-1" in s and "【高】" in s and "金额" in s


def test_build_focus_points():
    points = build_focus_points([_hit("high")])
    assert len(points) == 2  # 命中 1 条 + 固定复核提示
    assert points[-1]["rule_name"] == "通用提示"
    assert points[0]["rule_code"] == "R001"
