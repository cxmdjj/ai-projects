"""两场景全链路自动化演示(无需真实 LLM API Key)。

用脚本化 MockLLM + 真实种子数据驱动任务引擎完整跑通「商品目录优化」(7 轮)与
「客户行为分析」(6 轮)两个演示场景,每轮覆盖: 追问 → 工具调用(只读 SQL / 附件检索 /
沙箱命令 / 结果文件)→ 证据 → 六部分阶段结论;末轮演示上下文摘要压缩与最终报告。

前置: 先跑 scripts/seed_data.py 与 scripts/demo_assets_generator.py。
用法:  uv run --project backend python backend/demo_scripts/run_demo_conversation.py
       uv run --project backend python backend/demo_scripts/run_demo_conversation.py --scenario catalog
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 导入 app 前固定运行环境(不依赖 cwd)
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / 'backend' / 'data' / 'app.db'}"
os.environ["STORAGE_ROOT"] = str(ROOT / "backend" / "storage")
os.environ["JWT_SECRET"] = "demo-secret-0123456789abcdef0123456789abcdef"
os.environ["LOG_DIR"] = str(ROOT / "backend" / "logs")
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.core.config_manager import config_manager  # noqa: E402
from app.engine.llm_client import MockLLMClient, mock_text_deltas, mock_tool_call_deltas  # noqa: E402
from app.models import ContextSummary, Conversation, User  # noqa: E402
from app.services import ws_manager as wsm  # noqa: E402
from app.services.attachment_service import AttachmentService  # noqa: E402
from app.services.task_service import TaskService  # noqa: E402
from app.workers import task_worker  # noqa: E402

# ============================== 场景一 · 商品目录优化(7 轮) ==============================

CATALOG_SQL_CVR_BY_CATEGORY = """
SELECT ca.category_name,
       ROUND(SUM(c.order_cnt) * 100.0 / SUM(k.click_cnt), 2) AS cvr_pct
FROM scn1_conversions c
JOIN (SELECT stat_date, product_id, SUM(click_cnt) AS click_cnt FROM scn1_clicks GROUP BY stat_date, product_id) k
  ON c.stat_date = k.stat_date AND c.product_id = k.product_id
JOIN scn1_products p ON p.product_id = c.product_id
JOIN scn1_categories ca ON ca.category_id = p.category_id
WHERE c.stat_date >= '2026-08-02'
GROUP BY ca.category_name
ORDER BY cvr_pct ASC
"""

CATALOG_SQL_PRICE_BAND = """
SELECT CASE WHEN p.price BETWEEN 200 AND 300 THEN '200-300元' ELSE '其他价格带' END AS price_band,
       ROUND(SUM(c.order_cnt) * 100.0 / SUM(k.click_cnt), 2) AS cvr_pct,
       ROUND(AVG(p.price / p.cost_price), 2) AS markup
FROM scn1_conversions c
JOIN (SELECT stat_date, product_id, SUM(click_cnt) AS click_cnt FROM scn1_clicks GROUP BY stat_date, product_id) k
  ON c.stat_date = k.stat_date AND c.product_id = k.product_id
JOIN scn1_products p ON p.product_id = c.product_id
WHERE p.category_id IN (
  SELECT category_id FROM scn1_categories WHERE category_name = '厨房小家电'
  OR parent_id = (SELECT category_id FROM scn1_categories WHERE category_name = '厨房小家电')
)
GROUP BY price_band
"""

CATALOG_SQL_KEYWORD_CTR = """
SELECT e.search_keyword,
       SUM(e.exposure_cnt) AS exposure,
       ROUND(SUM(k.click_cnt) * 100.0 / SUM(e.exposure_cnt), 2) AS ctr_pct
FROM scn1_search_exposures e
JOIN scn1_clicks k
  ON e.stat_date = k.stat_date AND e.product_id = k.product_id AND e.search_keyword = k.search_keyword
WHERE e.stat_date >= '2026-08-02'
GROUP BY e.search_keyword
HAVING SUM(e.exposure_cnt) > 10000
ORDER BY ctr_pct ASC
"""

CATALOG_SQL_SHELF = """
SELECT COUNT(*) AS new_products FROM scn1_products WHERE on_shelf_date >= '2026-08-02'
"""

CATALOG_ROUNDS = [
    {
        "user": "帮我看看最近60天商品目录的整体表现,有没有明显的转化问题?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": CATALOG_SQL_CVR_BY_CATEGORY, "purpose": "按类目对比点击→下单转化率"}, "c1"),
            mock_text_deltas("类目转化率差异明显:厨房小家电仅1.01%,低于大盘2.5%。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "最近60天商品目录是否存在明显的转化率问题",
                "key_metrics": [
                    {"metric_name": "全站点击→下单转化率", "metric_value": "2.5%", "metric_unit": "%", "metric_period": "2026-08-02~09-30"},
                    {"metric_name": "厨房小家电点击→下单转化率", "metric_value": "1.01%", "metric_unit": "%", "metric_period": "2026-08-02~09-30"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn1_clicks/scn1_conversions",
                     "evidence_text": "厨房小家电点击→下单转化率 1.01%,仅为大盘 2.5% 的 40%,是转化洼地",
                     "related_metric": "点击→下单转化率", "confidence": "high"},
                ],
                "conclusion_text": "目录整体转化 2.5%,但厨房小家电类目显著偏低(1.01%),影响范围涉及该品类全部商品。",
                "missing_data_text": "该品类价格分布与竞品价格数据,用于判断是否价格因素导致。",
                "next_action_text": ["下钻厨房小家电价格带与转化率的关系", "补充竞品价格数据对比"],
            }, "c2"),
        ],
    },
    {
        "user": "为什么厨房小家电转化这么低?和价格有关吗?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": CATALOG_SQL_PRICE_BAND, "purpose": "厨房小家电价格带×转化率"}, "c3"),
            mock_text_deltas("200-300元价格带转化仅0.55%,且加价率1.42显著高于其他类目1.15。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "厨房小家电转化率偏低是否与定价相关",
                "key_metrics": [
                    {"metric_name": "200-300元价格带转化率", "metric_value": "0.55%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "厨房小家电价格/成本比", "metric_value": "1.42", "metric_unit": "倍", "metric_period": "当前"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn1_products",
                     "evidence_text": "厨房小家电 200-300 元价格带转化率仅 0.55%,明显低于品类均值 1.01%;价格/成本比 1.42,高于其他类目 1.15(溢价约 23%)",
                     "related_metric": "价格带转化率", "confidence": "high"},
                ],
                "conclusion_text": "价格是主因:厨房小家电溢价约 23%,200-300 元主力价格带转化率仅 0.55%。",
                "missing_data_text": "竞品同款价格数据,确认市场可接受价格区间。",
                "next_action_text": ["上传竞品价格数据进行验证", "评估 200-300 元商品调价空间"],
            }, "c4"),
        ],
    },
    {
        "user": "我上传了竞品价格对照表,结合附件数据分析溢价情况",
        "steps": [
            mock_tool_call_deltas("text_search", {"query": "破壁机 竞品价格", "source": "attachments", "top_k": 5}, "c5"),
            mock_text_deltas("竞品对照表显示破壁机品类本品价格比竞品高 12%-25%。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "厨房小家电溢价是否超出市场可接受范围",
                "key_metrics": [
                    {"metric_name": "破壁机品类价格差幅", "metric_value": "+12%~+25%", "metric_unit": "%", "metric_period": "竞品对照表(2026-09)"},
                ],
                "evidence_list": [
                    {"source_type": "attachment", "source_name": "竞品价格对照.csv",
                     "evidence_text": "附件竞品对照表显示破壁机/电饭煲/空气炸锅本品价格普遍高于同配置竞品 12%-25%",
                     "related_metric": "价格差幅", "confidence": "high"},
                ],
                "conclusion_text": "附件证据印证了溢价判断: 厨房小家电定价系统性高于竞品 12%-25%,是转化率偏低的核心归因。",
                "missing_data_text": "溢价后的毛利结构与降价空间测算。",
                "next_action_text": ["检查搜索曝光效率,确认是否存在被埋没的优质商品", "对溢价商品做调价模拟"],
            }, "c6"),
        ],
    },
    {
        "user": "搜索曝光效率怎么样?有没有被埋没的好商品?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": CATALOG_SQL_KEYWORD_CTR, "purpose": "关键词点击率排名"}, "c7"),
            mock_text_deltas("静音破壁机关键词点击率仅0.37%,远低于全站3.39%——在售破壁机均未主打静音卖点,搜索相关性差。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "搜索曝光效率是否存在问题",
                "key_metrics": [
                    {"metric_name": "静音破壁机关键词点击率", "metric_value": "0.37%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "全站平均点击率", "metric_value": "3.39%", "metric_unit": "%", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn1_search_exposures/scn1_clicks",
                     "evidence_text": "「静音破壁机」关键词点击率 0.37%,仅为全站平均 3.39% 的 1/9;商品名/主图未含静音卖点导致搜索相关性差",
                     "related_metric": "关键词点击率", "confidence": "high"},
                ],
                "conclusion_text": "搜索曝光浪费严重: 高需求词「静音破壁机」点击率 0.37%,商品卖点表达与用户搜索意图不匹配。",
                "missing_data_text": "商品标题/主图卖点字段数据。",
                "next_action_text": ["对破壁机商品标题补充静音卖点并测 CTR", "汇总全部发现输出商品目录优化报告"],
            }, "c8"),
        ],
    },
    {
        "user": "综合起来,给出商品目录优化最终报告",
        "steps": [
            mock_tool_call_deltas("result_file", {
                "file_name": "商品目录优化行动清单.md", "file_type": "markdown",
                "content": "# 商品目录优化行动清单\n1. 厨房小家电调价: 200-300 元价格带下调 10%;\n2. 破壁机标题补充静音卖点;\n3. 两周后复盘转化率。",
            }, "c9"),
            mock_text_deltas("已生成行动清单文件,以下是最终报告。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "商品目录优化的完整归因与行动方案",
                "key_metrics": [
                    {"metric_name": "大盘转化率", "metric_value": "2.5%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "厨房小家电转化率", "metric_value": "1.01%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "静音破壁机点击率", "metric_value": "0.37%", "metric_unit": "%", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn1_clicks/scn1_conversions", "evidence_text": "厨房小家电转化 1.01% vs 大盘 2.5%", "related_metric": "转化率", "confidence": "high"},
                    {"source_type": "database", "source_name": "scn1_products", "evidence_text": "200-300 元价格带转化 0.55%,加价率 1.42 vs 其他类目 1.15", "related_metric": "价格带转化率", "confidence": "high"},
                    {"source_type": "attachment", "source_name": "竞品价格对照.csv", "evidence_text": "本品价格高于竞品 12%-25%", "related_metric": "价格差幅", "confidence": "high"},
                    {"source_type": "database", "source_name": "scn1_search_exposures", "evidence_text": "静音破壁机关键词 CTR 0.37% vs 全站 3.39%", "related_metric": "点击率", "confidence": "high"},
                ],
                "conclusion_text": "商品目录核心问题是厨房小家电'贵且表达差': 定价溢价 23% 导致 200-300 元主力价格带转化仅 0.55%,同时商品卖点(静音)缺失导致高需求搜索词点击率仅 0.37%。影响范围: 厨房小家电全品类 60 个商品。",
                "missing_data_text": "调价后的毛利测算与竞品动态价格监控数据。",
                "next_action_text": ["厨房小家电 200-300 元价格带下调 10% 并两周后复盘", "破壁机商品标题补充静音卖点并 A/B 测试", "建立竞品价格月度监控机制"],
            }, "c10"),
        ],
    },
    {
        "user": "刚才说调价10%,如果按这个幅度模拟一下影响?",
        "steps": [
            # 沙箱程序 cwd 为 workspace/cmd/,模拟数据写入该目录供沙箱读取
            mock_tool_call_deltas("file_write", {"path": "cmd/price_sim.json", "content": '{"band": [200, 300], "discount": 0.10, "cvr": 0.0055, "clicks": 5200}'}, "c11"),
            mock_tool_call_deltas("command_exec", {
                "command": "import json\nwith open('price_sim.json', encoding='utf-8') as f:\n    d = json.load(f)\ncvr_new = d['cvr'] * 1.25\norders_old = int(d['clicks'] * d['cvr'])\norders_new = int(d['clicks'] * cvr_new)\nprint(f'调价10%后转化率约 {cvr_new*100:.2f}%, 订单量从 {orders_old} 提升到 {orders_new}(+{(orders_new-orders_old)*100.0//max(orders_old,1):.0f}%)')",
            }, "c12"),
            mock_text_deltas("模拟显示调价10%可带来约25%的转化提升。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "厨房小家电调价 10% 的影响模拟",
                "key_metrics": [
                    {"metric_name": "调价后预估转化率", "metric_value": "0.69%", "metric_unit": "%", "metric_period": "模拟(基于价格弹性假设)"},
                    {"metric_name": "预估订单增幅", "metric_value": "+25%", "metric_unit": "%", "metric_period": "模拟"},
                ],
                "evidence_list": [
                    {"source_type": "command", "source_name": "price_sim.json",
                     "evidence_text": "沙箱内 Python 模拟: 价格-10% → 转化率约 0.69%(+25%),按当前点击量测算订单量同步提升 25%",
                     "related_metric": "预估转化率", "confidence": "medium"},
                ],
                "conclusion_text": "模拟结果显示调价 10% 可将 200-300 元价格带转化率从 0.55% 提升至约 0.69%,值得试点执行。",
                "missing_data_text": "真实价格弹性系数(当前为假设值 1.25)。",
                "next_action_text": ["对 10 个 SKU 试点调价 10% 并监控", "收集调价后真实弹性系数回填模型"],
            }, "c13"),
        ],
    },
    {
        "user": "归档这个结论,整理成最终报告",
        "steps": [
            mock_text_deltas("以下是本轮分析的最终归档报告(历史对话已自动压缩)。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "商品目录优化最终报告(归档)",
                "key_metrics": [
                    {"metric_name": "厨房小家电转化率(现状)", "metric_value": "1.01%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "调价后预估转化率", "metric_value": "0.69%", "metric_unit": "%", "metric_period": "模拟"},
                ],
                "evidence_list": [
                    {"source_type": "llm_inference", "source_name": "多轮分析汇总",
                     "evidence_text": "综合数据库查询、竞品附件、关键词漏斗与调价模拟四类证据,确认定价溢价与卖点缺失是核心归因",
                     "related_metric": "转化率", "confidence": "high"},
                ],
                "conclusion_text": "最终结论: 厨房小家电转化洼地的两大归因是定价溢价 23% 与静音卖点表达缺失;调价 10% 预计带来 25% 转化提升。",
                "missing_data_text": "真实价格弹性系数。",
                "next_action_text": ["执行试点调价并两周后复盘", "补充静音卖点并 A/B 测试", "将报告同步至商品运营周会"],
            }, "c14"),
        ],
    },
]

# ============================== 场景二 · 客户行为分析(6 轮) ==============================

BEHAVIOR_SQL_FUNNEL = """
SELECT
  COUNT(DISTINCT v.customer_id) AS visit_users,
  COUNT(DISTINCT ca.customer_id) AS cart_users,
  COUNT(DISTINCT o.customer_id) AS order_users
FROM scn2_visit_events v
LEFT JOIN scn2_cart_events ca ON ca.customer_id = v.customer_id
LEFT JOIN scn2_order_events o ON o.customer_id = v.customer_id
"""

BEHAVIOR_SQL_CHANNEL = """
SELECT v.channel,
       COUNT(*) AS visits,
       ROUND(COUNT(DISTINCT o.customer_id) * 100.0 / COUNT(DISTINCT v.customer_id), 2) AS visit_to_order_pct
FROM scn2_visit_events v
LEFT JOIN scn2_order_events o ON o.customer_id = v.customer_id
GROUP BY v.channel
"""

BEHAVIOR_SQL_ABANDON = """
SELECT ROUND(SUM(CASE WHEN o.customer_id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS abandon_pct,
       COUNT(*) AS cart_users
FROM (SELECT DISTINCT customer_id FROM scn2_cart_events) c
LEFT JOIN scn2_order_events o ON o.customer_id = c.customer_id
"""

BEHAVIOR_SQL_REPURCHASE = """
SELECT cu.member_level,
       ROUND(SUM(CASE WHEN order_cnt >= 2 THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN order_cnt >= 1 THEN 1 ELSE 0 END), 1) AS repurchase_pct
FROM (SELECT cu.customer_id, cu.member_level, COUNT(o.order_id) AS order_cnt
      FROM scn2_customers cu LEFT JOIN scn2_order_events o ON o.customer_id = cu.customer_id
      GROUP BY cu.customer_id, cu.member_level) t
GROUP BY member_level
"""

BEHAVIOR_ROUNDS = [
    {
        "user": "看看最近60天客户行为的总漏斗:访问→加购→下单的转化情况如何?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": BEHAVIOR_SQL_FUNNEL, "purpose": "总漏斗用户数"}, "d1"),
            mock_text_deltas("总漏斗: 访问用户约2000人,其中约半数加购,下单用户约1100人。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "最近60天客户行为总漏斗表现",
                "key_metrics": [
                    {"metric_name": "访问用户数", "metric_value": "约2000", "metric_unit": "人", "metric_period": "近60天"},
                    {"metric_name": "加购用户数", "metric_value": "约1000", "metric_unit": "人", "metric_period": "近60天"},
                    {"metric_name": "下单用户数", "metric_value": "约1100", "metric_unit": "人", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn2_visit_events/scn2_cart_events/scn2_order_events",
                     "evidence_text": "访问→下单用户转化约 55%,但加购用户中仍有约 38% 未产生订单", "related_metric": "漏斗转化", "confidence": "high"},
                ],
                "conclusion_text": "整体漏斗在加购→下单环节存在明显流失,需要定位流失集中的渠道与人群。",
                "missing_data_text": "分渠道漏斗与流失时间窗口数据。",
                "next_action_text": ["按渠道拆解转化率定位问题渠道", "分析加购后未下单的流失时间窗口"],
            }, "d2"),
        ],
    },
    {
        "user": "按渠道拆解一下访问→下单转化率,哪个渠道拖后腿?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": BEHAVIOR_SQL_CHANNEL, "purpose": "分渠道转化率"}, "d3"),
            mock_text_deltas("渠道A贡献39.5%访问但转化仅1.00%,B/C渠道为3.57%/3.44%。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "哪个渠道拉低了整体转化率",
                "key_metrics": [
                    {"metric_name": "渠道A访问占比", "metric_value": "39.5%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "渠道A访问→下单转化率", "metric_value": "1.00%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "渠道B/C转化率", "metric_value": "3.57%/3.44%", "metric_unit": "%", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn2_visit_events/scn2_order_events",
                     "evidence_text": "渠道 A 贡献 39.5% 访问但转化率仅 1.00%,仅为 B/C 渠道(3.57%/3.44%)的约 1/3.5,是主要拖累项",
                     "related_metric": "访问→下单转化率", "confidence": "high"},
                ],
                "conclusion_text": "渠道 A 是转化洼地: 贡献近四成流量但转化只有 B/C 的三分之一。",
                "missing_data_text": "渠道 A 的投放素材与落地页数据,判断流量质量问题。",
                "next_action_text": ["上传渠道投放明细分析流量质量", "下钻渠道 A 用户加购后行为"],
            }, "d4"),
        ],
    },
    {
        "user": "我上传了渠道投放明细表,看看渠道A的投放有什么问题",
        "steps": [
            mock_tool_call_deltas("text_search", {"query": "渠道 落地页 素材", "source": "attachments", "top_k": 8}, "d5"),
            mock_text_deltas("渠道A的投放素材都是促销主题,但落地页却是新品首发页——素材与落地页不匹配。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "渠道 A 投放效率低的原因",
                "key_metrics": [
                    {"metric_name": "渠道A素材-落地页不匹配占比", "metric_value": "100%", "metric_unit": "%", "metric_period": "投放明细表(2026-08)"},
                ],
                "evidence_list": [
                    {"source_type": "attachment", "source_name": "渠道投放明细.xlsx",
                     "evidence_text": "渠道 A 投放素材为促销主题(满减/秒杀),落地页却指向新品首发页,用户预期与页面内容错位导致转化低",
                     "related_metric": "访问→下单转化率", "confidence": "high"},
                ],
                "conclusion_text": "渠道 A 转化低的直接原因是投放素材与落地页不匹配,属于投放执行质量问题。",
                "missing_data_text": "各素材组合的落地点击率与停留时长。",
                "next_action_text": ["修正渠道 A 落地页指向(促销素材→促销页)", "继续分析加购用户的流失时间窗口"],
            }, "d6"),
        ],
    },
    {
        "user": "加购后没下单的用户,一般多久就流失了?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": BEHAVIOR_SQL_ABANDON, "purpose": "加购未下单流失占比"}, "d7"),
            mock_text_deltas("加购用户中约38%在3天窗口内未下单,其中大部分集中在24小时内流失。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "加购用户的流失时间窗口",
                "key_metrics": [
                    {"metric_name": "加购后3天未下单占比", "metric_value": "37.9%", "metric_unit": "%", "metric_period": "近60天加购用户"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn2_cart_events/scn2_order_events",
                     "evidence_text": "约 37.9% 的加购用户在加购后 3 天窗口内未下单即流失,召回窗口非常短",
                     "related_metric": "加购流失率", "confidence": "high"},
                ],
                "conclusion_text": "加购后 3 天是黄金召回窗口,当前约 38% 用户在此窗口流失,需要自动召回机制。",
                "missing_data_text": "流失用户的触达渠道与优惠敏感度。",
                "next_action_text": ["对加购未下单用户做 24 小时优惠券召回", "分析会员等级与复购的关系"],
            }, "d8"),
        ],
    },
    {
        "user": "不同会员等级的复购情况怎么样?",
        "steps": [
            mock_tool_call_deltas("db_query", {"sql": BEHAVIOR_SQL_REPURCHASE, "purpose": "会员等级复购率"}, "d9"),
            mock_text_deltas("L1复购率19.8%,L3+达56.7%~90.2%,高等级会员复购率约为L1的3.2倍。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "会员等级与复购率的关系",
                "key_metrics": [
                    {"metric_name": "L1 复购率", "metric_value": "19.8%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "L3 复购率", "metric_value": "56.7%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "L4 复购率", "metric_value": "90.2%", "metric_unit": "%", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn2_customers/scn2_order_events",
                     "evidence_text": "L3+ 复购率(56.7%~90.2%)约为 L1(19.8%)的 3.2 倍,会员成长显著放大复购",
                     "related_metric": "复购率", "confidence": "high"},
                ],
                "conclusion_text": "会员等级是复购的核心杠杆,资源应向 L1→L2 晋级倾斜。",
                "missing_data_text": "会员晋级周期与权益敏感度。",
                "next_action_text": ["设计 L1→L2 加速晋级活动", "汇总全部发现输出客户行为分析最终报告"],
            }, "d10"),
        ],
    },
    {
        "user": "综合全部发现,给出客户行为分析的最终报告",
        "steps": [
            mock_text_deltas("以下是客户行为分析的最终报告(历史对话已自动压缩)。")[:-1]
            + mock_tool_call_deltas("submit_analysis_result", {
                "problem_definition": "客户行为分析最终报告",
                "key_metrics": [
                    {"metric_name": "渠道A访问→下单转化率", "metric_value": "1.00%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "加购3天流失率", "metric_value": "37.9%", "metric_unit": "%", "metric_period": "近60天"},
                    {"metric_name": "L3+复购率", "metric_value": "56.7%~90.2%", "metric_unit": "%", "metric_period": "近60天"},
                ],
                "evidence_list": [
                    {"source_type": "database", "source_name": "scn2_visit_events/scn2_order_events", "evidence_text": "渠道A转化1.00%,仅B/C渠道约1/3.5", "related_metric": "转化率", "confidence": "high"},
                    {"source_type": "attachment", "source_name": "渠道投放明细.xlsx", "evidence_text": "渠道A投放素材与落地页不匹配", "related_metric": "转化率", "confidence": "high"},
                    {"source_type": "database", "source_name": "scn2_cart_events", "evidence_text": "加购用户37.9%在3天窗口流失", "related_metric": "流失率", "confidence": "high"},
                    {"source_type": "database", "source_name": "scn2_customers", "evidence_text": "L3+复购率为L1的3.2倍", "related_metric": "复购率", "confidence": "high"},
                ],
                "conclusion_text": "客户行为三大发现: ①渠道A投放素材与落地页错位导致转化仅1.00%;②加购后3天流失37.9%,召回窗口极短;③会员复购杠杆明显(L3+是L1的3.2倍)。影响范围: 渠道A全部流量、近四成加购用户。",
                "missing_data_text": "召回触达通道的打开率数据。",
                "next_action_text": ["修复渠道A落地页指向并重投", "上线加购24小时优惠券自动召回", "启动L1→L2加速晋级活动", "将报告同步至用户增长周会"],
            }, "d11"),
        ],
    },
]


# ============================== 驱动逻辑 ==============================


class DemoMockLLM(MockLLMClient):
    """演示用 mock: 流式走脚本;非流式(摘要压缩/兜底)返回抽取式演示摘要。"""

    async def chat(self, messages, tools=None, response_format=None):
        text = ""
        for m in reversed(messages):
            if m["role"] == "user" and not m["content"].startswith(("[历史", "请基于", "你是经营")):
                text = m["content"]
                break
        content = f"[历史对话摘要] 业务问题: {text[:60]}…;各轮阶段结论、关键指标与证据已归档,待补充数据清单保留。"
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


async def run_scenario(name: str, rounds: list[dict], attachment_uploads: list[str] | None = None) -> None:
    print(f"\n{'=' * 64}\n场景: {name}  共 {len(rounds)} 轮\n{'=' * 64}")
    db = SessionLocal()
    try:
        config_manager.reload(db)
        # 演示上下文摘要压缩: 调低触发阈值与保留窗口(顺带演示配置热更新)
        config_manager.set(db, "analysis.summary_trigger_msgs", "8")
        config_manager.set(db, "analysis.summary_keep_recent", "4")
        # 演示沙箱命令执行: 临时开启功能开关(默认关闭)
        config_manager.set(db, "feature.command_exec", "on")

        user = db.query(User).first()
        if user is None:
            user = User(external_user_id="demo", username="demo", display_name="演示用户", role="analyst", status="active")
            db.add(user)
            db.commit()
            db.refresh(user)
        conv = Conversation(user_id=user.id, title=f"演示-{name}")
        db.add(conv)
        db.commit()
        db.refresh(conv)

        # 上传演示附件(若需要)
        for asset in attachment_uploads or []:
            asset_path = ROOT / "docs" / "demo" / "assets" / asset
            if asset_path.exists():
                att = AttachmentService(db).save_upload(user, conv.id, asset, asset_path.read_bytes())
                await asyncio.to_thread(AttachmentService(db).run_parse_pipeline, att.id)
                print(f"[附件] 已上传并解析 {asset} (attachment_id={att.id})")

        # 事件收集(替换广播,不依赖真实 WS 连接)
        wsm.ws_manager.broadcast = _collect

        for i, rnd in enumerate(rounds, start=1):
            print(f"\n--- 第 {i} 轮 · 用户追问 ---\n>>> {rnd['user']}")
            _events.clear()
            task_worker.get_llm_client = lambda r=rnd: DemoMockLLM(script=[list(s) for s in r["steps"]], stream_delay=0.005)
            task = TaskService(db).create(conv.id, user.id, rnd["user"])
            assert task is not None, "单任务锁冲突(前一轮未结束)"
            await task_worker.run(task.id)
            db.expire_all()  # 清空身份映射缓存,读到 worker 会话提交后的最新状态
            task = TaskService(db).get(task.id)
            status = task.task_status
            print(f"[任务] status={status} current_step={task.current_step}")
            for e in _events:
                if e["type"] == "tool_start":
                    print(f"  [工具] {e['tool_name']} 开始执行")
                elif e["type"] == "tool_finish":
                    print(f"  [工具] {e['tool_name']} 完成: {e['tool_result_summary'][:80]}")
                elif e["type"] == "message_delta":
                    print(f"  [流式] {e['delta_text'][:60]}")
                elif e["type"] == "result_ready":
                    print(f"  [结果] 六部分结构化结果已生成 result_id={e['result_id']}")
            assert status == "success", f"第 {i} 轮任务失败: {task.error_message}"
            if any(e["type"] == "result_ready" for e in _events):
                print("  ✓ 六部分结果已落库,结果文件已生成(可下载)")

        summaries = db.query(ContextSummary).filter(ContextSummary.conversation_id == conv.id).all()
        print(f"\n[上下文摘要] 触发 {len(summaries)} 段压缩(阈值=8条消息, 配置热更新生效):")
        for s in summaries:
            print(f"  - seq {s.start_seq_no}~{s.end_seq_no}: {s.summary_text[:60]}...")
        assert summaries, "长对话应触发上下文摘要压缩"
        print(f"\n✓ 场景 {name} 演示完成: {len(rounds)} 轮全部 success, 六部分结果与结果文件已生成, 摘要压缩已触发")
    finally:
        config_manager.set(db, "analysis.summary_trigger_msgs", "30")  # 还原默认
        config_manager.set(db, "analysis.summary_keep_recent", "12")  # 还原默认
        config_manager.set(db, "feature.command_exec", "off")  # 还原默认
        db.close()


_events: list[dict] = []


async def _collect(conversation_id: int, event: dict) -> None:
    _events.append(event)
    from app.services.ws_manager import ws_manager

    ws_manager.push_event(event.get("task_id") or 0, event)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["catalog", "behavior", "both"], default="both")
    args = parser.parse_args()
    if args.scenario in ("catalog", "both"):
        await run_scenario("商品目录优化", CATALOG_ROUNDS, attachment_uploads=["竞品价格对照.csv"])
    if args.scenario in ("behavior", "both"):
        await run_scenario("客户行为分析", BEHAVIOR_ROUNDS, attachment_uploads=["渠道投放明细.xlsx"])


if __name__ == "__main__":
    asyncio.run(main())
