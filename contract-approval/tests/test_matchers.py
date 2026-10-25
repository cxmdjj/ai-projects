from app.rules.matchers import match_rule
from app.schemas.contract import build_clause, build_field


def _context(full_text="", basic=None, clauses=None, pages=None):
    return {
        "full_text": full_text,
        "pages": pages or [(1, full_text)],
        "basic": basic or {},
        "clauses": clauses or {},
    }


def test_regex_hit_and_miss():
    ctx = _context("合同期满前 30 日双方未书面提出异议的,本合同自动续期一年。")
    r = match_rule("regex", {"field": "full_text", "pattern": r"自动续[约期]"}, ctx)
    assert r.matched and "自动续期" in r.evidence_text and r.evidence_position == "第1页"
    r2 = match_rule("regex", {"field": "full_text", "pattern": r"自动续[约期]"}, _context("本合同一年一签。"))
    assert not r2.matched


def test_regex_no_match_inverse():
    ctx = _context("本合同一年一签,无续约安排。")
    r = match_rule("regex", {"field": "full_text", "pattern": r"自动续[约期]", "hit_if": "no_match"}, ctx)
    assert r.matched


def test_keyword():
    ctx = _context("本合同期满自动续约一年。")
    r = match_rule("keyword", {"field": "full_text", "keywords": ["自动续期", "自动续约"]}, ctx)
    assert r.matched
    r2 = match_rule("keyword", {"field": "full_text", "keywords": ["自动续期"]}, ctx)
    assert not r2.matched


def test_field_missing():
    basic = {"amount": build_field("amount", value="100", source_text="金额100元")}
    ctx = _context(basic=basic)
    assert not match_rule("field_missing", {"field": "basic.amount"}, ctx).matched
    assert match_rule("field_missing", {"field": "basic.our_party"}, ctx).matched
    # 多字段 any 模式
    assert match_rule("field_missing", {"field": "basic.amount,basic.our_party"}, ctx).matched
    assert not match_rule("field_missing",
                          {"field": "basic.amount,basic.our_party", "missing_mode": "all"}, ctx).matched


def test_clause_missing_and_vague():
    ctx = _context(clauses={"acceptance": build_clause("acceptance", heading="第五条 验收条款",
                                                       content="按行业通行标准验收。")})
    # 条款存在且不命中 vague → 未命中
    assert not match_rule("clause_missing", {"field": "clause.acceptance"}, ctx).matched
    # 条款存在但含糊 → 命中
    r = match_rule("clause_missing",
                   {"field": "clause.acceptance", "vague_pattern": r"按(?:行业|国家|通常|一般)[^。\n]{0,8}标准"}, ctx)
    assert r.matched
    # 条款缺失 → 命中
    assert match_rule("clause_missing", {"field": "clause.ip"}, ctx).matched


def test_value_compare():
    ctx = _context("预付款比例为合同总价的 50%;设备验收合格后 90 日内支付尾款。")
    r = match_rule("value_compare",
                   {"field": "full_text", "pattern": r"预付款?(?:比例|金额)?[^%\d]{0,20}(\d+(?:\.\d+)?)\s*%",
                    "threshold": 30, "operator": ">"}, ctx)
    assert r.matched
    r2 = match_rule("value_compare",
                    {"field": "full_text", "pattern": r"(?:验收合格后|验收后)[^日\d]{0,15}(\d{1,3})\s*日",
                     "threshold": 45, "operator": ">"}, ctx)
    assert r2.matched  # 90 > 45
    r3 = match_rule("value_compare",
                    {"field": "full_text", "pattern": r"(?:验收合格后|验收后)[^日\d]{0,15}(\d{1,3})\s*日",
                     "threshold": 200, "operator": ">"}, ctx)
    assert not r3.matched
    # 提取不到数值 → 不计命中
    assert not match_rule("value_compare",
                          {"field": "full_text", "pattern": r"违约金[^%\d]{0,10}(\d+)%",
                           "threshold": 5, "operator": ">"}, ctx).matched


def test_multiline_flat_matching():
    """PDF 换行不应破坏跨行匹配(乙方所在地人民\n法院管辖)。"""
    ctx = _context("提交乙方所在地人民\n法院管辖。")
    r = match_rule("regex",
                   {"field": "full_text",
                    "pattern": r"(?:乙方|卖方)所在地[^。\n]{0,20}(?:管辖|仲裁)"}, ctx)
    assert r.matched
