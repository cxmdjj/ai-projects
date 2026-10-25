"""结构化结果 Schema 与校验(需求文档第 11 节 六部分输出)。"""

import json

from jsonschema import ValidationError, validate

SUBMIT_TOOL_NAME = "submit_analysis_result"

RESULT_JSON_SCHEMA = {
    "type": "object",
    "required": [
        "problem_definition",
        "key_metrics",
        "evidence_list",
        "conclusion_text",
        "missing_data_text",
        "next_action_text",
    ],
    "properties": {
        "problem_definition": {"type": "string", "minLength": 2},
        "key_metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["metric_name", "metric_value", "metric_unit", "metric_period"],
                "properties": {
                    "metric_name": {"type": "string"},
                    "metric_value": {"type": ["string", "number"]},
                    "metric_unit": {"type": "string"},
                    "metric_period": {"type": "string"},
                },
            },
        },
        "evidence_list": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_type", "source_name", "evidence_text", "related_metric", "confidence"],
                "properties": {
                    "source_type": {
                        "enum": ["database", "attachment", "workspace_file", "text_search", "command", "llm_inference"]
                    },
                    "source_name": {"type": "string"},
                    "evidence_text": {"type": "string"},
                    "related_metric": {"type": "string"},
                    "confidence": {"enum": ["high", "medium", "low"]},
                },
            },
        },
        "conclusion_text": {"type": "string"},
        "missing_data_text": {"type": "string"},
        # 至少 1 条即可通过 schema,不足 2 条时由 normalize 补齐兜底建议(验收标准要求 ≥2)
        "next_action_text": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
}

SUBMIT_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": SUBMIT_TOOL_NAME,
        "description": (
            "提交本轮归因分析的六部分结构化结果。必须在完成数据查询与证据整理后调用,"
            "key_metrics/evidence_list 至少各 1 项,next_action_text 至少 2 条。"
        ),
        "parameters": RESULT_JSON_SCHEMA,
    },
}

DEFAULT_NEXT_ACTIONS = [
    "补充缺失数据后复核本结论",
    "将结论与下一步建议同步至业务周会跟进",
]


def validate_and_normalize(payload: dict) -> dict:
    """jsonschema 校验 + 规范化;校验失败抛 ValueError(带可读错误)。"""
    validate(instance=payload, schema=RESULT_JSON_SCHEMA)
    payload["problem_definition"] = str(payload["problem_definition"]).strip()
    payload["conclusion_text"] = str(payload["conclusion_text"]).strip()
    payload["missing_data_text"] = str(payload["missing_data_text"]).strip()
    payload["key_metrics"] = [
        {
            "metric_name": str(m.get("metric_name", "")),
            "metric_value": m.get("metric_value"),
            "metric_unit": str(m.get("metric_unit", "")),
            "metric_period": str(m.get("metric_period", "")),
        }
        for m in payload["key_metrics"]
    ]
    payload["evidence_list"] = [
        {
            "source_type": e["source_type"],
            "source_name": str(e.get("source_name", "")),
            "evidence_text": str(e.get("evidence_text", "")),
            "related_metric": str(e.get("related_metric", "")),
            "confidence": e["confidence"],
        }
        for e in payload["evidence_list"]
    ]
    actions = [str(a).strip() for a in payload["next_action_text"] if str(a).strip()]
    while len(actions) < 2:  # 验收标准: 下一步建议至少 2 条
        actions.append(DEFAULT_NEXT_ACTIONS[len(actions) % len(DEFAULT_NEXT_ACTIONS)])
    payload["next_action_text"] = actions
    return payload


def parse_payload(text: str) -> dict:
    """从文本中解析六部分 JSON(兼容 {…} 包裹或纯 JSON)。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def format_schema_error(err: ValidationError) -> str:
    path = ".".join(str(p) for p in err.absolute_path) or "根节点"
    return f"字段 {path} 不合法: {err.message}"
