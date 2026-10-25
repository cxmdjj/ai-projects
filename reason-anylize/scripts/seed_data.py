"""演示场景种子数据生成(确定性,random.seed(42))。

用法(用 backend 的 uv 环境运行):
    uv run --project backend python scripts/seed_data.py                    # 全量种子到默认 SQLite
    uv run --project backend python scripts/seed_data.py --scenario catalog # 仅场景一
    uv run --project backend python scripts/seed_data.py --db-url "mysql+pymysql://user:pass@host:3306/reason_analyze?charset=utf8mb4"
    uv run --project backend python scripts/seed_data.py --scale 0.5        # 数据量倍率

生成两个场景的演示数据并在末尾打印「预埋业务真相核对表」,docs/demo 演示脚本引用该表数字。
"""

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

ROOT = Path(__file__).resolve().parents[1]

# 确保可导入 app.models(backend 项目包)
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    Scn1Category,
    Scn1Click,
    Scn1Conversion,
    Scn1Product,
    Scn1SearchExposure,
    Scn2CartEvent,
    Scn2Customer,
    Scn2OrderEvent,
    Scn2VisitEvent,
)

RNG = random.Random(42)

# ============================== 场景一 · 商品目录优化 ==============================

CATALOG_DAYS = 60
CATALOG_END = date(2026, 9, 30)  # 数据截至 2026-09-30,"最近 60 天"= 8/2~9/30

TOP_CATEGORIES = ["家电", "数码", "家居", "服饰", "美妆", "食品"]
LEVEL2 = {
    "家电": ["厨房小家电", "大家电", "个护电器"],
    "数码": ["手机", "电脑办公", "影音娱乐"],
    "家居": ["家纺", "收纳清洁"],
    "服饰": ["男装", "女装"],
    "美妆": ["护肤", "彩妆"],
    "食品": ["休闲零食", "粮油调味"],
}
LEVEL3 = {
    "厨房小家电": ["破壁机", "电饭煲", "空气炸锅"],
    "大家电": ["冰箱", "洗衣机"],
}

# 类目关键词池(搜索曝光词)
CATEGORY_KEYWORDS = {
    "厨房小家电": ["破壁机", "电饭煲", "空气炸锅", "厨房电器"],
    "大家电": ["冰箱", "洗衣机", "家电"],
    "个护电器": ["吹风机", "电动牙刷", "剃须刀"],
    "手机": ["手机", "旗舰手机", "手机壳"],
    "电脑办公": ["笔记本电脑", "键盘", "显示器"],
    "影音娱乐": ["耳机", "音箱", "投影仪"],
    "家纺": ["四件套", "被子", "枕头"],
    "收纳清洁": ["收纳箱", "拖把", "清洁用品"],
    "男装": ["男士外套", "T恤", "牛仔裤"],
    "女装": ["连衣裙", "女装", "针织衫"],
    "护肤": ["面霜", "精华", "面膜"],
    "彩妆": ["口红", "粉底", "眼影"],
    "休闲零食": ["零食大礼包", "坚果", "薯片"],
    "粮油调味": ["大米", "食用油", "调味料"],
}

# 价格带设定: 厨房小家电 40% 商品落在 200-300 元且转化仅 0.6%
PREMIUM_BAND = (200.0, 300.0)
BAND_SHARE = 0.4
BAND_CVR = 0.006
KITCHEN_NON_BAND_CVR = 0.018
BASE_CVR = 0.028
BASE_CTR = 0.035
MUTE_CTR = 0.004  # 静音破壁机关键词点击率(商品名不含"静音",相关性差)
KITCHEN_MARKUP = 1.32  # 厨房小家电加价率
NORMAL_MARKUP = 1.15

MUTE_PRODUCT_NAMES = [
    "小熊破壁机PBJ-208", "美的破壁机BL80", "九阳破壁机L18", "苏泊尔破壁机SP902",
    "奥克斯破壁机AUX-66", "荣事达破壁机RSD-33", "摩飞破壁机MR-120", "利仁破壁机LR-55",
    "小熊破壁机PBJ-310", "美的破壁机BL60", "九阳破壁机Y1", "苏泊尔破壁机SP605",
    "奥克斯破壁机AUX-88", "荣事达破壁机RSD-51", "摩飞破壁机MR-950", "利仁破壁机LR-77",
    "美的破壁机BL45", "九阳破壁机L12", "苏泊尔破壁机SP208", "小熊破壁机PBJ-150",
]


def _gen_categories():
    cats = []
    cid = 1
    for top in TOP_CATEGORIES:
        cats.append({"category_id": cid, "category_name": top, "parent_id": None, "level": 1, "sort_order": cid})
        top_id = cid
        cid += 1
        for lv2 in LEVEL2[top]:
            cats.append({"category_id": cid, "category_name": lv2, "parent_id": top_id, "level": 2, "sort_order": cid})
            lv2_id = cid
            cid += 1
            for lv3 in LEVEL3.get(lv2, []):
                cats.append({"category_id": cid, "category_name": lv3, "parent_id": lv2_id, "level": 3, "sort_order": cid})
                cid += 1
    return cats


def _gen_products():
    """300 个商品: 厨房小家电 60 个(20 破壁机/20 电饭煲/20 空气炸锅),其余 240 个均分到其他二级类目。"""
    categories = _gen_categories()
    by_name = {c["category_name"]: c for c in categories}
    products = []
    pid = 1

    # 厨房小家电: 60 个,40% 落入 200-300 元价格带(转化 0.6%)
    for i in range(60):
        cost = round(RNG.uniform(80, 240), 2)
        if RNG.random() < BAND_SHARE:
            price = round(RNG.uniform(*PREMIUM_BAND), 2)  # 直接落价格带
        else:
            price = round(cost * RNG.uniform(1.1, 1.25), 2)
        if price > 300:
            price = round(RNG.uniform(150, 199), 2)
        products.append(
            {
                "product_id": pid,
                "sku_code": f"SKU{pid:05d}",
                "product_name": "",
                "category_id": by_name["厨房小家电"]["category_id"],
                "price": price,
                "cost_price": cost,
                "brand": RNG.choice(["小熊", "美的", "九阳", "苏泊尔", "奥克斯"]),
                "shelf_status": "on",
                "on_shelf_date": CATALOG_END - timedelta(days=RNG.randint(10, 300)),
            }
        )
        pid += 1
    # 前 20 个破壁机 = 名称不含"静音"的商品(平台在售破壁机均未主打静音卖点,
    # 用户搜索"静音破壁机"时只能展示这些相关性差的商品 → 关键词点击率仅 0.4%)
    blenders = [p for p in products if p["category_id"] == by_name["厨房小家电"]["category_id"]][:20]
    for idx, p in enumerate(blenders):
        p["product_name"] = MUTE_PRODUCT_NAMES[idx]
        p["category_id"] = by_name["破壁机"]["category_id"]
    # 其余厨房小家电商品命名
    kitchen_rest = [p for p in products if p["category_id"] == by_name["厨房小家电"]["category_id"]]
    for i, p in enumerate(kitchen_rest):
        if i < 20:
            p["product_name"] = f"智能电饭煲{RNG.choice(['小熊','美的','苏泊尔','九阳'])}{i+1:02d}"
            p["category_id"] = by_name["电饭煲"]["category_id"]
        else:
            p["product_name"] = f"空气炸锅{RNG.choice(['小熊','美的','苏泊尔','奥克斯'])}{i+1-20:02d}"
            p["category_id"] = by_name["空气炸锅"]["category_id"]

    # 其余 240 个商品均分到其他 11 个二级类目
    other_lv2 = [c for c in categories if c["level"] == 2 and c["category_name"] != "厨房小家电"]
    for i in range(240):
        cat = other_lv2[i % len(other_lv2)]
        cost = round(RNG.uniform(80, 240), 2)
        price = round(cost * NORMAL_MARKUP, 2)
        kw = RNG.choice(CATEGORY_KEYWORDS[cat["category_name"]])
        products.append(
            {
                "product_id": pid,
                "sku_code": f"SKU{pid:05d}",
                "product_name": f"{RNG.choice(['小熊','美的','小米','海尔','京东京造','优品'])}{kw}{RNG.choice(['标准款','升级款','经典款','轻奢款'])}{i+1:02d}",
                "category_id": cat["category_id"],
                "price": price,
                "cost_price": cost,
                "brand": RNG.choice(["小熊", "美的", "小米", "海尔", "京东京造"]),
                "shelf_status": "on",
                "on_shelf_date": CATALOG_END - timedelta(days=RNG.randint(10, 300)),
            }
        )
        pid += 1
    return products, categories


def gen_catalog(engine, scale: float) -> None:
    products, categories = _gen_products()
    by_name = {c["category_name"]: c for c in categories}
    kitchen_id = by_name["厨房小家电"]["category_id"]
    blender_id = by_name["破壁机"]["category_id"]
    kitchen_family = {kitchen_id} | {c["category_id"] for c in categories if c["parent_id"] == kitchen_id}

    def product_cvr(p):
        if p["category_id"] in kitchen_family:
            return BAND_CVR if PREMIUM_BAND[0] <= p["price"] <= PREMIUM_BAND[1] else KITCHEN_NON_BAND_CVR
        return BASE_CVR

    exposures, clicks, conversions = [], [], []
    for day_offset in range(CATALOG_DAYS):
        d = CATALOG_END - timedelta(days=CATALOG_DAYS - 1 - day_offset)
        for p in products:
            cat_name = next((c["category_name"] for c in categories if c["category_id"] == p["category_id"]), "通用")
            keywords = CATEGORY_KEYWORDS.get(cat_name, ["通用"])[:]
            if p["category_id"] == blender_id:
                keywords = ["破壁机", "静音破壁机"]  # 破壁机商品两词分流
            rows = max(2, round(RNG.randint(2, 3) * scale))
            for _ in range(rows):
                keyword = RNG.choice(keywords)
                exposure = int(RNG.expovariate(1 / 220)) + 1
                ctr = MUTE_CTR if keyword == "静音破壁机" and "静音" not in p["product_name"] else BASE_CTR
                click = sum(1 for _ in range(exposure) if RNG.random() < ctr)
                cvr = product_cvr(p)
                order = sum(1 for _ in range(click) if RNG.random() < cvr)
                uv = max(1, int(exposure * RNG.uniform(0.7, 0.9)))
                exposures.append({"stat_date": d, "product_id": p["product_id"], "search_keyword": keyword,
                                  "exposure_cnt": exposure, "exposure_uv": uv})
                clicks.append({"stat_date": d, "product_id": p["product_id"], "search_keyword": keyword,
                               "click_cnt": click, "click_uv": max(0, int(click * RNG.uniform(0.6, 0.9)))})
                conversions.append({
                    "stat_date": d, "product_id": p["product_id"],
                    "order_cnt": order,
                    "order_uv": max(0, int(order * RNG.uniform(0.6, 0.9))),
                    "gmv": round(order * p["price"] * RNG.uniform(0.9, 1.4), 2) if order else 0,
                    "refund_cnt": sum(1 for _ in range(order) if RNG.random() < 0.03),
                })
    _bulk(engine, Scn1Category, categories)
    _bulk(engine, Scn1Product, products)
    _bulk(engine, Scn1SearchExposure, exposures)
    _bulk(engine, Scn1Click, clicks)
    _bulk(engine, Scn1Conversion, conversions)
    print(f"[场景一] 类目 {len(categories)} / 商品 {len(products)} / 曝光 {len(exposures)} / 点击 {len(clicks)} / 转化 {len(conversions)} 行")


# ============================== 场景二 · 客户行为分析 ==============================

BEHAVIOR_DAYS = 60
BEHAVIOR_END = datetime(2026, 9, 30, 23, 59, 0)

CHANNELS = ["A", "B", "C"]
CHANNEL_WEIGHTS = [0.44, 0.31, 0.25]  # 渠道 A 贡献约 40% 访问
LEVEL_ORDER_BASE = {  # 各等级下单次数分布(复购率 L3+ ≈ 80%,L1 ≈ 25% → 3.2 倍)
    "L1": [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
    "L2": [0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3],
    "L3": [1, 2, 2, 2, 2, 3, 3, 3, 4, 4],
    "L4": [2, 2, 3, 3, 3, 4, 4, 5, 5, 6],
}
CHANNEL_ORDER_MULT = {"A": 0.4, "B": 1.4, "C": 1.4}  # 渠道 A 用户下单能力显著更差
LEVEL_WEIGHTS = [("L1", 0.60), ("L2", 0.25), ("L3", 0.12), ("L4", 0.03)]
CARTER_SHARE = 0.5
ABANDON_SHARE = 0.25  # 加购后 3 天窗口内未下单流失(叠加天然零下单客户后约 35%)
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
          "苏州", "天津", "长沙", "郑州", "青岛", "厦门", "合肥", "宁波", "佛山", "东莞"]

MEMBER_LEVELS = ["L1", "L2", "L3", "L4"]
AGE_BANDS = ["18-25", "26-35", "36-45", "46+"]
PAGE_TYPES = ["home", "category", "product", "cart", "order"]
PAGE_WEIGHTS = [0.30, 0.25, 0.30, 0.10, 0.05]
DEVICES = ["app", "h5", "pc"]
DEVICE_WEIGHTS = [0.6, 0.3, 0.1]


def _weighted_choice(options, weights):
    return RNG.choices(options, weights=weights, k=1)[0]


def gen_behavior(engine, scale: float) -> None:
    n_customers = int(2000 * scale)
    customers, visits, carts, orders = [], [], [], []
    order_no = 1

    for cid in range(1, n_customers + 1):
        channel = _weighted_choice(CHANNELS, CHANNEL_WEIGHTS)
        level = _weighted_choice([l for l, _ in LEVEL_WEIGHTS], [w for _, w in LEVEL_WEIGHTS])
        customer = {
            "customer_id": cid,
            "city": RNG.choice(CITIES),
            "age_band": RNG.choice(AGE_BANDS),
            "gender": RNG.choice(["男", "女"]),
            "member_level": level,
            "register_date": (BEHAVIOR_END - timedelta(days=RNG.randint(30, 700))).date(),
            "channel": channel,
        }
        customers.append(customer)

        # 访问事件
        n_visits = int(RNG.expovariate(1 / 40)) + 1
        for _ in range(n_visits):
            t = BEHAVIOR_END - timedelta(seconds=RNG.randint(0, BEHAVIOR_DAYS * 86400 - 1))
            visits.append({
                "customer_id": cid,
                "event_time": t,
                "page_type": _weighted_choice(PAGE_TYPES, PAGE_WEIGHTS),
                "channel": channel if RNG.random() < 0.7 else RNG.choice(CHANNELS),
                "device_type": _weighted_choice(DEVICES, DEVICE_WEIGHTS),
                "session_id": f"s{cid}_{RNG.randint(0, 99999)}",
            })

        # 加购事件(50% 客户有加购行为)
        is_carter = RNG.random() < CARTER_SHARE
        n_cart = 0
        if is_carter:
            n_cart = int(RNG.expovariate(1 / 20)) + 1
            for _ in range(n_cart):
                t = BEHAVIOR_END - timedelta(seconds=RNG.randint(0, BEHAVIOR_DAYS * 86400 - 1))
                carts.append({
                    "customer_id": cid,
                    "event_time": t,
                    "product_id": RNG.randint(1, 300),
                    "quantity": RNG.randint(1, 3),
                    "unit_price": round(RNG.uniform(30, 400), 2),
                })

        # 下单事件(等级分布 × 渠道倍率;加购客户 35% 在 3 天窗口内未下单即流失)
        base_orders = RNG.choice(LEVEL_ORDER_BASE[level])
        n_orders = max(0, round(base_orders * CHANNEL_ORDER_MULT[channel]))
        if is_carter and RNG.random() < ABANDON_SHARE:
            n_orders = 0  # 加购后流失
        for i in range(n_orders):
            if is_carter and carts and cid in [c["customer_id"] for c in carts]:
                last_cart = max(c["event_time"] for c in carts if c["customer_id"] == cid)
                t = last_cart + timedelta(seconds=RNG.randint(3600, 3 * 86400 - 1))  # 加购后 3 天内
            else:
                t = BEHAVIOR_END - timedelta(seconds=RNG.randint(0, BEHAVIOR_DAYS * 86400 - 1))
            orders.append({
                "order_id": f"O{order_no:07d}",
                "customer_id": cid,
                "order_time": t,
                "order_amount": round(RNG.uniform(60, 1200), 2),
                "order_status": _weighted_choice(["paid", "paid", "paid", "paid", "refunded"], [0.9, 0.9, 0.9, 0.9, 0.1]),
                "channel": channel,
            })
            order_no += 1

    _bulk(engine, Scn2Customer, customers)
    _bulk(engine, Scn2VisitEvent, visits)
    _bulk(engine, Scn2CartEvent, carts)
    _bulk(engine, Scn2OrderEvent, orders)
    print(f"[场景二] 客户 {len(customers)} / 访问 {len(visits)} / 加购 {len(carts)} / 下单 {len(orders)} 行")


# ============================== 通用工具 ==============================


def _bulk(engine, model, rows, chunk: int = 5000) -> None:
    if not rows:
        return
    from sqlalchemy import insert

    with engine.begin() as conn:
        for i in range(0, len(rows), chunk):
            conn.execute(insert(model), rows[i : i + chunk])


DEMO_MODELS = [
    Scn1Category, Scn1Product, Scn1SearchExposure, Scn1Click, Scn1Conversion,
    Scn2Customer, Scn2VisitEvent, Scn2CartEvent, Scn2OrderEvent,
]


def _clear(engine, models) -> None:
    """清空演示业务表(幂等重跑)。"""
    from sqlalchemy import delete

    with engine.begin() as conn:
        for model in models:
            conn.execute(delete(model))
    print(f"已清空 {len(models)} 张演示业务表")


def _verify(engine) -> None:
    """打印预埋业务真相核对表(docs/demo 演示脚本引用这些数字)。"""
    print("\n========== 预埋业务真相核对表 ==========")
    with engine.connect() as conn:
        # 场景一(点击/转化均按 日期+商品 聚合,转化表无关键词维度)
        overall = conn.execute(text(
            "SELECT ROUND(SUM(c.order_cnt)*100.0/SUM(kc.click_cnt),2) FROM "
            "(SELECT stat_date, product_id, SUM(order_cnt) AS order_cnt FROM scn1_conversions GROUP BY stat_date, product_id) c "
            "JOIN (SELECT stat_date, product_id, SUM(click_cnt) AS click_cnt FROM scn1_clicks GROUP BY stat_date, product_id) kc "
            "ON c.stat_date=kc.stat_date AND c.product_id=kc.product_id"
        )).scalar()
        kitchen = conn.execute(text(
            "SELECT ROUND(SUM(c.order_cnt)*100.0/SUM(kc.click_cnt),2) FROM "
            "(SELECT stat_date, product_id, SUM(order_cnt) AS order_cnt FROM scn1_conversions GROUP BY stat_date, product_id) c "
            "JOIN (SELECT stat_date, product_id, SUM(click_cnt) AS click_cnt FROM scn1_clicks GROUP BY stat_date, product_id) kc "
            "ON c.stat_date=kc.stat_date AND c.product_id=kc.product_id "
            "JOIN scn1_products p ON p.product_id=c.product_id "
            "WHERE p.category_id IN (SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电' "
            "OR parent_id=(SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电'))"
        )).scalar()
        band = conn.execute(text(
            "SELECT ROUND(SUM(c.order_cnt)*100.0/SUM(kc.click_cnt),2) FROM "
            "(SELECT stat_date, product_id, SUM(order_cnt) AS order_cnt FROM scn1_conversions GROUP BY stat_date, product_id) c "
            "JOIN (SELECT stat_date, product_id, SUM(click_cnt) AS click_cnt FROM scn1_clicks GROUP BY stat_date, product_id) kc "
            "ON c.stat_date=kc.stat_date AND c.product_id=kc.product_id "
            "JOIN scn1_products p ON p.product_id=c.product_id "
            "WHERE p.category_id IN (SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电' "
            "OR parent_id=(SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电')) "
            "AND p.price BETWEEN 200 AND 300"
        )).scalar()
        mute = conn.execute(text(
            "SELECT ROUND(SUM(k.click_cnt)*100.0/SUM(e.exposure_cnt),2) FROM scn1_search_exposures e "
            "JOIN scn1_clicks k ON e.stat_date=k.stat_date AND e.product_id=k.product_id AND e.search_keyword=k.search_keyword "
            "WHERE e.search_keyword='静音破壁机'"
        )).scalar()
        avg_ctr = conn.execute(text(
            "SELECT ROUND(SUM(k.click_cnt)*100.0/SUM(e.exposure_cnt),2) FROM scn1_search_exposures e "
            "JOIN scn1_clicks k ON e.stat_date=k.stat_date AND e.product_id=k.product_id AND e.search_keyword=k.search_keyword"
        )).scalar()
        markup = conn.execute(text(
            "SELECT ROUND(AVG(p.price/p.cost_price),2) FROM scn1_products p "
            "WHERE p.category_id IN (SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电' "
            "OR parent_id=(SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电'))"
        )).scalar()
        markup_other = conn.execute(text(
            "SELECT ROUND(AVG(p.price/p.cost_price),2) FROM scn1_products p "
            "WHERE p.category_id NOT IN (SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电' "
            "OR parent_id=(SELECT category_id FROM scn1_categories WHERE category_name='厨房小家电'))"
        )).scalar()
        print(f"[场景一·商品目录优化]")
        print(f"  大盘点击→下单转化率: {overall}% (预期约 2.8%)")
        print(f"  厨房小家电点击→下单转化率: {kitchen}% (预期约 1.1%)")
        print(f"  厨房小家电 200-300 元价格带转化率: {band}% (预期约 0.6%)")
        print(f"  「静音破壁机」关键词点击率: {mute}% vs 全站平均 {avg_ctr}% (预期 0.4% vs 3.5%)")
        print(f"  厨房小家电价格/成本比: {markup} vs 其他类目 {markup_other} (预期高约 15%)")

        # 场景二
        chan_share = conn.execute(text(
            "SELECT channel, COUNT(*) FROM scn2_visit_events GROUP BY channel"
        )).all()
        total_visits = sum(r[1] for r in chan_share)
        print(f"[场景二·客户行为分析]")
        for ch, cnt in chan_share:
            orders_ch = conn.execute(text(
                "SELECT COUNT(*) FROM scn2_order_events WHERE channel=:ch"
            ), {"ch": ch}).scalar()
            print(f"  渠道 {ch}: 访问占比 {cnt*100.0/total_visits:.1f}%, 访问→下单转化率 {orders_ch*100.0/cnt:.2f}% (预期 A 约 1.2%,B/C 明显更高)")
        repurchase = conn.execute(text(
            "SELECT member_level, "
            "ROUND(SUM(CASE WHEN order_cnt>=2 THEN 1 ELSE 0 END)*100.0/SUM(CASE WHEN order_cnt>=1 THEN 1 ELSE 0 END),1) "
            "FROM (SELECT cu.customer_id, cu.member_level, COUNT(o.order_id) AS order_cnt FROM scn2_customers cu "
            "LEFT JOIN scn2_order_events o ON o.customer_id=cu.customer_id "
            "GROUP BY cu.customer_id, cu.member_level) t "
            "GROUP BY member_level"
        )).all()
        for level, rate in repurchase:
            print(f"  会员 {level} 复购率: {rate}% (预期 L3+ 约为 L1 的 3.2 倍)")
        abandon = conn.execute(text(
            "SELECT ROUND(SUM(CASE WHEN o.customer_id IS NULL THEN 1 ELSE 0 END)*100.0/COUNT(*),1) "
            "FROM (SELECT DISTINCT customer_id FROM scn2_cart_events) c "
            "LEFT JOIN scn2_order_events o ON o.customer_id=c.customer_id"
        )).scalar()
        print(f"  加购客户中 3 天窗口内未下单占比: {abandon}% (预期约 35%)")
    print("==========================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="演示场景种子数据生成")
    parser.add_argument("--db-url", default=f"sqlite:///{ROOT / 'backend' / 'data' / 'app.db'}")
    parser.add_argument("--scenario", choices=["catalog", "behavior", "both"], default="both")
    parser.add_argument("--scale", type=float, default=1.0, help="数据量倍率")
    args = parser.parse_args()

    engine = create_engine(args.db_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    print(f"数据库: {args.db_url}  场景: {args.scenario}  倍率: {args.scale}")
    scenario_models = {
        "catalog": DEMO_MODELS[:5],
        "behavior": DEMO_MODELS[5:],
        "both": DEMO_MODELS,
    }[args.scenario]
    _clear(engine, scenario_models)
    if args.scenario in ("catalog", "both"):
        gen_catalog(engine, args.scale)
    if args.scenario in ("behavior", "both"):
        gen_behavior(engine, args.scale)
    _verify(engine)
    engine.dispose()


if __name__ == "__main__":
    main()
