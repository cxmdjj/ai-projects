"""中文大写金额 → 数字转换。

支持:壹贰叁肆伍陆柒捌玖 / 零〇 / 拾佰仟万亿 / 元整角分(小数部分仅做容错解析)。
示例:"伍拾万元整" → 500000;"壹拾贰万捌仟元整" → 128000。
"""
import re

_DIGITS = {
    "零": 0, "〇": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5,
    "陆": 6, "柒": 7, "捌": 8, "玖": 9, "一": 1, "二": 2, "三": 3,
    "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "两": 2,
}
_UNITS = {"拾": 10, "佰": 100, "仟": 1000, "十": 10, "百": 100, "千": 1000}
_BIG_UNITS = {"万": 10_000, "亿": 100_000_000}

_CN_AMOUNT_RE = re.compile(r"[零〇壹贰叁肆伍陆柒捌玖一二三四五六七八九十两拾佰仟万亿]+")


def chinese_amount_to_int(text: str) -> int | None:
    """将中文大写金额字符串转为整数,失败返回 None。"""
    s = str(text).strip()
    # 去掉"元/圆/整/正/块"等后缀
    s = re.sub(r"[元圆整正块]+$", "", s)
    if not s:
        return None
    total = 0          # 亿/万级累计
    section = 0        # 当前小节(万以内)
    number = 0         # 当前数字
    seen_digit = False
    for ch in s:
        if ch in _DIGITS:
            number = _DIGITS[ch]
            seen_digit = True
        elif ch in _UNITS:
            if not seen_digit:
                # "拾五" 等省略了开头的"一"
                number = 1
            section += number * _UNITS[ch]
            number = 0
            seen_digit = False
        elif ch in _BIG_UNITS:
            if not seen_digit and section == 0:
                section = 1
            section += number
            number = 0
            seen_digit = False
            total += section * _BIG_UNITS[ch]
            section = 0
        else:
            return None
    total += section + number
    if not seen_digit and total == 0:
        return None
    return total
