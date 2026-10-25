"""解析提取:基本信息 8 字段 + 8 类条款切分。

原则:正则宽松匹配(容忍全角/半角、空白、标点差异),每个字段保留
原文片段与定位信息;提取失败标记 missing 而非静默返回空。
"""
import re

from app.schemas.contract import CLAUSE_DEFS, build_clause, build_field
from app.utils.chinese_num import chinese_amount_to_int

# ---------- 预处理 ----------

_FULLWIDTH_MAP = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ（）％：；、，",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz()%:;, ",
)


def normalize_text(text: str) -> str:
    """统一换行、折叠空白、全角转半角。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_FULLWIDTH_MAP)
    text = re.sub(r"[ \t　]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ---------- 定位辅助 ----------

def find_page(pages, fragment: str | None) -> str | None:
    """在分页文本中定位片段所在页码。"""
    if not fragment:
        return None
    for page_no, page_text in pages:
        if fragment in page_text:
            return f"第{page_no}页"
    return None


def _clean_date(value: str) -> str:
    return re.sub(r"\s+", "", value)


# ---------- 基本信息 8 字段 ----------

CONTRACT_NO_RE = re.compile(r"合同编号\s*[：:]\s*([A-Za-z0-9\-—–]+)")

PARTY_PATTERNS = [
    re.compile(r"甲方[（(][^（）()]*[）)][：:]\s*([^\n。;；,，]+)"),
    re.compile(r"甲方\s*[：:]\s*([^\n。;；,，]+)"),
]
COUNTERPARTY_PATTERNS = [
    re.compile(r"乙方[（(][^（）()]*[）)][：:]\s*([^\n。;；,，]+)"),
    re.compile(r"乙方\s*[：:]\s*([^\n。;；,，]+)"),
]

AMOUNT_ARABIC_RE = re.compile(r"(?:合同)?(?:总)?金额[^0-9]{0,15}([0-9][0-9,，]*(?:\.[0-9]+)?)\s*元")
AMOUNT_CHINESE_RE = re.compile(r"(?:人民币|RMB)\s*([零〇壹贰叁肆伍陆柒捌玖一二三四五六七八九十两拾佰仟万亿]+)")

_DATE_RE = r"[0-9]{4}\s*年\s*[0-9]{1,2}\s*月\s*[0-9]{1,2}\s*日"
_DATE_RE2 = r"[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}日?"
EFFECTIVE_PATTERNS = [
    re.compile(rf"自\s*({_DATE_RE})\s*(?:起)?(?:生效|起算)"),
    re.compile(rf"(?:生效日期|生效时间|生效日)\s*[：:]\s*({_DATE_RE}|{_DATE_RE2})"),
    re.compile(rf"({_DATE_RE})\s*生效"),
]
EXPIRY_PATTERNS = [
    re.compile(rf"至\s*({_DATE_RE})\s*(?:止|到期|届满|结束|为止)"),
    re.compile(rf"(?:到期日|到期时间|到期日期|届满日)\s*[：:]\s*({_DATE_RE}|{_DATE_RE2})"),
    re.compile(rf"({_DATE_RE})\s*(?:止|到期|届满)"),
]

_CN_NUM = "零〇壹贰叁肆伍陆柒捌玖一二三四五六七八九十两拾佰仟万亿"


def extract_title(text: str, pages) -> dict:
    """合同标题:首个非空且不含编号/主体的行。"""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.search(r"编号|甲方|乙方|签订日期", line):
            continue
        return build_field("contract_title", value=line, source_text=line, position=find_page(pages, line))
    return build_field("contract_title")


def extract_contract_no(text: str, pages) -> dict:
    m = CONTRACT_NO_RE.search(text)
    if m:
        return build_field("contract_no", value=m.group(1), source_text=text[max(0, m.start() - 10):m.end() + 10],
                           position=find_page(pages, m.group(1)))
    return build_field("contract_no")


def extract_party(text: str, pages, counterparty: bool = False) -> dict:
    patterns = COUNTERPARTY_PATTERNS if counterparty else PARTY_PATTERNS
    field = "counterparty" if counterparty else "our_party"
    for pat in patterns:
        m = pat.search(text)
        if m:
            value = m.group(1).strip()
            return build_field(field, value=value, source_text=text[max(0, m.start() - 5):m.end() + 5],
                               position=find_page(pages, value))
    return build_field(field)


def extract_amount(text: str, pages) -> dict:
    """金额双通道:阿拉伯数字 + 中文大写。"""
    m = AMOUNT_ARABIC_RE.search(text)
    if m:
        value = m.group(1).replace(",", "").replace("，", "")
        return build_field("amount", value=value, source_text=text[max(0, m.start() - 10):m.end() + 15],
                           position=find_page(pages, m.group(1)))
    m = AMOUNT_CHINESE_RE.search(text)
    if m:
        num = chinese_amount_to_int(m.group(1))
        if num is not None:
            return build_field("amount", value=str(num),
                               source_text=text[max(0, m.start() - 10):m.end() + 10],
                               position=find_page(pages, m.group(1)))
    return build_field("amount")


def extract_currency(text: str, pages, amount_source: str | None) -> dict:
    context = amount_source or text
    if re.search(r"美元|USD", context):
        value = "USD"
    elif re.search(r"欧元|EUR", context):
        value = "EUR"
    elif re.search(r"人民币|RMB|￥", context):
        value = "CNY"
    else:
        return build_field("currency")
    return build_field("currency", value=value, source_text=context, position=find_page(pages, context))


def extract_date(text: str, pages, effective: bool = True) -> dict:
    field = "effective_date" if effective else "expiry_date"
    patterns = EFFECTIVE_PATTERNS if effective else EXPIRY_PATTERNS
    for pat in patterns:
        m = pat.search(text)
        if m:
            value = _clean_date(m.group(1))
            return build_field(field, value=value, source_text=text[max(0, m.start() - 8):m.end() + 8],
                               position=find_page(pages, value))
    return build_field(field)


def extract_basic_info(text: str, pages) -> list[dict]:
    """提取 8 个基本信息字段。"""
    title = extract_title(text, pages)
    amount = extract_amount(text, pages)
    return [
        title,
        extract_contract_no(text, pages),
        extract_party(text, pages, counterparty=False),
        extract_party(text, pages, counterparty=True),
        amount,
        extract_currency(text, pages, amount.get("source_text")),
        extract_date(text, pages, effective=True),
        extract_date(text, pages, effective=False),
    ]


# ---------- 条款切分 ----------

HEADING_RE = re.compile(r"第[一二三四五六七八九十百0-9]+条[:\:、\s]*([^\n。]{0,30})")
_SENTENCE_SPLIT_RE = re.compile(r"[。;；\n]")


def _classify_heading(title_part: str) -> list[str]:
    """按关键词将条标题分类到条款类别(可能同时命中多个类别)。"""
    matched = []
    for cdef in CLAUSE_DEFS:
        if any(kw in title_part for kw in cdef["keywords"]):
            matched.append(cdef["clause"])
    return matched


def _sentence_for_keywords(content: str, keywords: list[str]) -> str | None:
    """在内容中找包含某类别关键词的句子(用于"交付与验收条款"这类复合条款)。"""
    best = None
    for sent in _SENTENCE_SPLIT_RE.split(content):
        hits = sum(1 for kw in keywords if kw in sent)
        if hits >= 1 and (best is None or hits > best[0]):
            best = (hits, sent.strip())
    return best[1] if best else None


def _fallback_find_clause(text: str, cdef: dict) -> str | None:
    """兜底:无条结构时,找包含关键词的整行。"""
    kws = cdef["keywords"]
    for line in text.splitlines():
        hits = sum(1 for kw in kws if kw in line)
        if hits >= 2 or (hits >= 1 and ("条款" in line or len(line) > 15)):
            return line.strip()
    return None


def extract_clauses(text: str, pages) -> list[dict]:
    """切分 8 类条款:按"第X条"标题分段,复合标题按句子二次归属,缺失走兜底。"""
    headings = [(m.start(), m.group(0).strip(), m.group(1).strip()) for m in HEADING_RE.finditer(text)]
    found: dict[str, tuple[str, str]] = {}  # clause -> (heading, content)

    for i, (start, heading, title_part) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        content = text[start:end].strip()
        categories = _classify_heading(title_part)
        for cat in categories:
            if cat not in found:
                found[cat] = (heading, content)
        # 复合标题:其余类别按句子归属
        if len(categories) > 1:
            for cat in categories[1:]:
                if cat in found and found[cat][0] == heading:
                    continue
                sent = _sentence_for_keywords(content, next(c["keywords"] for c in CLAUSE_DEFS if c["clause"] == cat))
                if sent:
                    found.setdefault(cat, (heading, sent))

    result = []
    for cdef in CLAUSE_DEFS:
        cat = cdef["clause"]
        if cat in found:
            heading, content = found[cat]
            position = f"{heading} · {find_page(pages, heading)}" if find_page(pages, heading) else heading
            result.append(build_clause(cat, heading=heading, content=content, position=position))
        else:
            fallback = _fallback_find_clause(text, cdef)
            if fallback:
                result.append(build_clause(cat, heading=None, content=fallback,
                                           position=find_page(pages, fallback)))
            else:
                result.append(build_clause(cat))
    return result
