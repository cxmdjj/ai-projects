"""规则匹配器:五种 match_mode 的匹配逻辑。"""
import re

from app.enums import ExtractStatus
from app.schemas.contract import BASIC_LABELS, CLAUSE_LABELS


class MatchResult:
    def __init__(self, matched: bool, evidence_text: str | None = None,
                 evidence_position: str | None = None, detail: str | None = None):
        self.matched = matched
        self.evidence_text = evidence_text
        self.evidence_position = evidence_position
        self.detail = detail


# ---------- 上下文解析 ----------

def _flat(text: str) -> str:
    """压平文本:换行/连续空白折叠为单个空格,避免 PDF 换行破坏跨行匹配。"""
    return re.sub(r"\s+", " ", text).strip()


def resolve_field_text(cfg: dict, context: dict) -> tuple[str, str | None, str]:
    """按 cfg.field 取匹配文本(已压平)。返回 (文本, 定位, 字段中文名)。"""
    field = cfg.get("field") or "full_text"
    if field == "full_text":
        return _flat(context.get("full_text", "")), None, "合同全文"
    if field.startswith("basic."):
        key = field.split(".", 1)[1]
        rec = context.get("basic", {}).get(key)
        if rec and rec.get("status") == ExtractStatus.EXTRACTED.value:
            return _flat(rec.get("source_text") or context.get("full_text", "")), rec.get("position"), rec.get("label")
        return _flat(context.get("full_text", "")), None, BASIC_LABELS.get(key, key)
    if field.startswith("clause."):
        key = field.split(".", 1)[1]
        rec = context.get("clauses", {}).get(key)
        if rec and rec.get("status") == ExtractStatus.EXTRACTED.value:
            return _flat(rec.get("content") or ""), rec.get("position"), rec.get("label")
        return "", None, CLAUSE_LABELS.get(key, key)
    return _flat(context.get("full_text", "")), None, "合同全文"


def find_position(context: dict, fragment: str | None) -> str | None:
    """在分页文本中定位片段页码(忽略空白差异)。"""
    if not fragment:
        return None
    needle = re.sub(r"\s+", "", fragment)
    for page_no, page_text in context.get("pages", []):
        if needle in re.sub(r"\s+", "", page_text):
            return f"第{page_no}页"
    return None


def excerpt(text: str, m: re.Match, radius: int = 25) -> str:
    start = max(0, m.start() - radius)
    end = min(len(text), m.end() + radius)
    return text[start:end].replace("\n", " ").strip()


# ---------- 五种 match_mode ----------

def _match_regex(cfg: dict, context: dict) -> MatchResult:
    text, position, _ = resolve_field_text(cfg, context)
    pattern = cfg.get("pattern", "")
    if not pattern:
        return MatchResult(False, detail="规则未配置 pattern")
    found = re.search(pattern, text)
    hit_if = cfg.get("hit_if", "match")
    if hit_if == "no_match":
        if found is None:
            return MatchResult(True, evidence_text=f"未发现「{pattern[:40]}」相关内容",
                               evidence_position=position, detail="取反匹配命中")
        return MatchResult(False)
    if found is None:
        return MatchResult(False)
    fragment = excerpt(text, found)
    return MatchResult(True, evidence_text=fragment,
                       evidence_position=position or find_position(context, fragment),
                       detail=f"正则命中: {pattern[:60]}")


def _match_keyword(cfg: dict, context: dict) -> MatchResult:
    text, position, _ = resolve_field_text(cfg, context)
    keywords = cfg.get("keywords") or []
    match_any = cfg.get("match_any", True)
    hits = [kw for kw in keywords if kw in text]
    matched = (len(hits) > 0) if match_any else (len(hits) == len(keywords))
    if not matched:
        return MatchResult(False)
    kw = hits[0]
    idx = text.find(kw)
    fragment = text[max(0, idx - 25):idx + len(kw) + 25].replace("\n", " ").strip()
    return MatchResult(True, evidence_text=fragment,
                       evidence_position=position or find_position(context, fragment),
                       detail=f"关键词命中: {kw}")


def _match_field_missing(cfg: dict, context: dict) -> MatchResult:
    fields = [f.strip() for f in (cfg.get("field") or "").split(",") if f.strip()]
    missing_mode = cfg.get("missing_mode", "any")
    basic = context.get("basic", {})
    statuses = []
    for f in fields:
        key = f.split(".", 1)[1] if "." in f else f
        rec = basic.get(key)
        statuses.append(rec is None or rec.get("status") != ExtractStatus.EXTRACTED.value)
    matched = any(statuses) if missing_mode == "any" else all(statuses)
    if not matched:
        return MatchResult(False)
    missing_fields = [f for f, miss in zip(fields, statuses) if miss]
    labels = "、".join(BASIC_LABELS.get(f.split(".", 1)[1], f) for f in missing_fields)
    return MatchResult(True, evidence_text=f"未提取到「{labels}」信息",
                       evidence_position=None, detail=f"字段缺失: {labels}")


def _match_clause_missing(cfg: dict, context: dict) -> MatchResult:
    key = (cfg.get("field") or "").split(".", 1)[1]
    rec = context.get("clauses", {}).get(key)
    label = CLAUSE_LABELS.get(key, key)
    if rec is None or rec.get("status") != ExtractStatus.EXTRACTED.value:
        return MatchResult(True, evidence_text=f"合同中未找到{label}",
                           evidence_position=None, detail="条款缺失")
    vague_pattern = cfg.get("vague_pattern")
    if vague_pattern:
        content = rec.get("content") or ""
        m = re.search(vague_pattern, content)
        if m:
            fragment = excerpt(content, m)
            return MatchResult(True, evidence_text=fragment,
                               evidence_position=rec.get("position"),
                               detail="条款存在但约定含糊")
    return MatchResult(False)


_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
}


def _match_value_compare(cfg: dict, context: dict) -> MatchResult:
    text, position, _ = resolve_field_text(cfg, context)
    pattern = cfg.get("pattern", "")
    m = re.search(pattern, text) if pattern else None
    if m is None:
        return MatchResult(False, detail="未从原文提取到数值(不计命中)")
    try:
        value = float(m.group(1).replace(",", "").replace("，", ""))
    except (ValueError, IndexError):
        return MatchResult(False, detail="数值解析失败")
    threshold = float(cfg.get("threshold", 0))
    op = cfg.get("operator", ">")
    matched = _OPS.get(op, lambda a, b: a > b)(value, threshold)
    if not matched:
        return MatchResult(False)
    fragment = excerpt(text, m)
    return MatchResult(True, evidence_text=fragment,
                       evidence_position=position or find_position(context, fragment),
                       detail=f"提取值 {value:g} {op} 阈值 {threshold:g}")


_MATCHERS = {
    "regex": _match_regex,
    "keyword": _match_keyword,
    "field_missing": _match_field_missing,
    "clause_missing": _match_clause_missing,
    "value_compare": _match_value_compare,
}


def match_rule(match_mode: str, cfg: dict, context: dict) -> MatchResult:
    """按规则的 match_mode 分发匹配。未知模式不命中并记录 detail。"""
    matcher = _MATCHERS.get(match_mode)
    if matcher is None:
        return MatchResult(False, detail=f"未知 match_mode: {match_mode}")
    return matcher(cfg, context)
