"""结果文件渲染: markdown / html。"""

import html
import json


def render_markdown(payload: dict) -> str:
    lines = [
        "# 经营归因分析报告",
        "",
        "## 一、问题定义",
        "",
        payload.get("problem_definition", ""),
        "",
        "## 二、关键指标",
        "",
        "| 指标名称 | 指标值 | 单位 | 统计周期 |",
        "| --- | --- | --- | --- |",
    ]
    for m in payload.get("key_metrics", []):
        lines.append(
            f"| {m.get('metric_name', '')} | {m.get('metric_value', '')} | {m.get('metric_unit', '')} | {m.get('metric_period', '')} |"
        )
    lines += ["", "## 三、证据列表", ""]
    for i, e in enumerate(payload.get("evidence_list", []), start=1):
        lines.append(
            f"**证据 {i}**({e.get('source_type', '')} · {e.get('source_name', '')} · 置信度 {e.get('confidence', '')})"
        )
        lines.append("")
        lines.append(f"- {e.get('evidence_text', '')}")
        lines.append(f"- 关联指标: {e.get('related_metric', '')}")
        lines.append("")
    lines += ["## 四、归因结论", "", payload.get("conclusion_text", ""), "", "## 五、待补充数据", ""]
    missing = payload.get("missing_data_text", "")
    lines.append(missing if missing.strip() else "无")
    lines += ["", "## 六、下一步建议", ""]
    for i, a in enumerate(payload.get("next_action_text", []), start=1):
        lines.append(f"{i}. {a}")
    lines.append("")
    return "\n".join(lines)


def render_html(payload: dict, markdown: str | None = None) -> str:
    esc = html.escape
    metrics = "".join(
        f"<tr><td>{esc(str(m.get('metric_name','')))}</td><td>{esc(str(m.get('metric_value','')))}</td>"
        f"<td>{esc(str(m.get('metric_unit','')))}</td><td>{esc(str(m.get('metric_period','')))}</td></tr>"
        for m in payload.get("key_metrics", [])
    )
    evidence = "".join(
        f"<li><strong>{esc(str(e.get('source_type','')))} · {esc(str(e.get('source_name','')))}</strong>"
        f"(置信度 {esc(str(e.get('confidence','')))})<br/>{esc(str(e.get('evidence_text','')))}</li>"
        for e in payload.get("evidence_list", [])
    )
    actions = "".join(f"<li>{esc(str(a))}</li>" for a in payload.get("next_action_text", []))
    missing = esc(str(payload.get("missing_data_text", ""))) or "无"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>经营归因分析报告</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 860px; margin: 24px auto; padding: 0 16px; color: #222; line-height: 1.7; }}
h1 {{ border-bottom: 2px solid #1677ff; padding-bottom: 8px; }}
h2 {{ margin-top: 28px; color: #1677ff; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background: #f5f7fa; }}
</style>
</head>
<body>
<h1>经营归因分析报告</h1>
<h2>一、问题定义</h2>
<p>{esc(str(payload.get('problem_definition','')))}</p>
<h2>二、关键指标</h2>
<table><thead><tr><th>指标名称</th><th>指标值</th><th>单位</th><th>统计周期</th></tr></thead><tbody>{metrics}</tbody></table>
<h2>三、证据列表</h2>
<ol>{evidence}</ol>
<h2>四、归因结论</h2>
<p>{esc(str(payload.get('conclusion_text','')))}</p>
<h2>五、待补充数据</h2>
<p>{missing}</p>
<h2>六、下一步建议</h2>
<ol>{actions}</ol>
</body>
</html>"""
