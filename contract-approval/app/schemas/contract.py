"""合同解析结果结构:基本信息 8 字段 + 8 类条款。

每个字段均保留:value 提取值 / source_text 原文片段 / position 定位 / status 提取状态。
"""
from app.enums import ExtractStatus

# 基本信息 8 字段定义
BASIC_FIELDS = [
    {"field": "contract_title", "label": "合同标题"},
    {"field": "contract_no", "label": "合同编号"},
    {"field": "our_party", "label": "签约主体"},
    {"field": "counterparty", "label": "对方名称"},
    {"field": "amount", "label": "金额"},
    {"field": "currency", "label": "币种"},
    {"field": "effective_date", "label": "生效时间"},
    {"field": "expiry_date", "label": "到期时间"},
]

# 8 类条款定义(含用于分类的关键词)
CLAUSE_DEFS = [
    {"clause": "payment", "label": "付款条款", "keywords": ["付款", "支付", "预付款", "尾款", "结算"]},
    {"clause": "delivery", "label": "交付条款", "keywords": ["交付", "交货", "交付时间"]},
    {"clause": "acceptance", "label": "验收条款", "keywords": ["验收"]},
    {"clause": "breach", "label": "违约条款", "keywords": ["违约"]},
    {"clause": "confidentiality", "label": "保密条款", "keywords": ["保密"]},
    {"clause": "data", "label": "数据条款", "keywords": ["数据", "个人信息"]},
    {"clause": "ip", "label": "知识产权条款", "keywords": ["知识产权", "专利", "著作权", "商标"]},
    {"clause": "dispute", "label": "争议解决条款", "keywords": ["争议", "管辖", "仲裁", "法律适用"]},
]

CLAUSE_LABELS = {c["clause"]: c["label"] for c in CLAUSE_DEFS}
BASIC_LABELS = {f["field"]: f["label"] for f in BASIC_FIELDS}


def build_field(field: str, value=None, source_text=None, position=None) -> dict:
    label = BASIC_LABELS.get(field, field)
    return {
        "field": field,
        "label": label,
        "value": value,
        "source_text": source_text,
        "position": position,
        "status": ExtractStatus.EXTRACTED.value if value else ExtractStatus.MISSING.value,
    }


def build_clause(clause: str, heading=None, content=None, position=None) -> dict:
    label = CLAUSE_LABELS.get(clause, clause)
    return {
        "clause": clause,
        "label": label,
        "status": ExtractStatus.EXTRACTED.value if (heading or content) else ExtractStatus.MISSING.value,
        "heading": heading,
        "content": content,
        "position": position,
    }
