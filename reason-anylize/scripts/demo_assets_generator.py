"""生成演示上传素材(用于演示附件上传、解析与 text_search 证据检索):

- docs/demo/assets/竞品价格对照.csv: 30 行,厨房小家电竞品价格对比(展示溢价 15%+)
- docs/demo/assets/渠道投放明细.xlsx: 200 行,渠道 A/B/C 投放素材与落地页(展示渠道 A 素材与落地页不匹配)

用法: uv run --project backend python scripts/demo_assets_generator.py
"""

import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "assets"
RNG = random.Random(42)


def gen_competitor_csv() -> None:
    """竞品价格对照: 15 个厨房小家电商品 + 15 个其他类目商品。"""
    kitchen_products = [
        ("破壁机", "小熊破壁机PBJ-208", 269), ("破壁机", "美的破壁机BL80", 289), ("破壁机", "九阳破壁机L18", 259),
        ("电饭煲", "智能电饭煲01", 239), ("电饭煲", "智能电饭煲02", 259), ("空气炸锅", "空气炸锅01", 279),
        ("破壁机", "苏泊尔破壁机SP902", 299), ("电饭煲", "智能电饭煲03", 249), ("空气炸锅", "空气炸锅02", 289),
        ("破壁机", "奥克斯破壁机AUX-66", 279), ("电饭煲", "智能电饭煲04", 269), ("空气炸锅", "空气炸锅03", 259),
        ("破壁机", "荣事达破壁机RSD-33", 289), ("电饭煲", "智能电饭煲05", 259), ("空气炸锅", "空气炸锅04", 299),
    ]
    other_products = [
        ("手机", "小米手机X200", 2999), ("手机", "华为手机Nova15", 3199), ("笔记本电脑", "联想笔记本小新", 4999),
        ("四件套", "全棉四件套60支", 399), ("四件套", "水洗棉四件套", 329), ("洗面奶", "氨基酸洁面120g", 89),
        ("面霜", "保湿面霜50g", 159), ("吹风机", "负离子吹风机", 199), ("电动牙刷", "声波电动牙刷", 129),
        ("收纳箱", "透明收纳箱3件套", 79), ("零食大礼包", "坚果零食大礼包", 99), ("食用油", "压榨花生油5L", 129),
        ("耳机", "降噪蓝牙耳机", 499), ("键盘", "机械键盘87键", 349), ("台灯", "护眼台灯", 199),
    ]
    rows = []
    for cat, name, our_price in kitchen_products:
        comp_price = round(our_price / RNG.uniform(1.12, 1.25), 2)  # 竞品便宜 12%-25%
        rows.append({
            "品类": cat, "商品名称": name, "本品价格(元)": our_price, "竞品价格(元)": comp_price,
            "价格差幅": f"+{round((our_price / comp_price - 1) * 100, 1)}%",
            "竞品渠道": RNG.choice(["京东自营", "天猫旗舰店", "拼多多百亿补贴"]),
            "备注": "同配置同容量",
        })
    for cat, name, our_price in other_products:
        comp_price = round(our_price / RNG.uniform(0.92, 1.08), 2)  # 其他类目价格基本持平
        rows.append({
            "品类": cat, "商品名称": name, "本品价格(元)": our_price, "竞品价格(元)": comp_price,
            "价格差幅": f"{round((our_price / comp_price - 1) * 100, 1):+}%",
            "竞品渠道": RNG.choice(["京东自营", "天猫旗舰店", "拼多多百亿补贴"]),
            "备注": "同配置同容量",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "竞品价格对照.csv", index=False, encoding="utf-8-sig")
    print(f"已生成 {OUT / '竞品价格对照.csv'} ({len(rows)} 行)")


def gen_channel_ads_xlsx() -> None:
    """渠道投放明细: 渠道 A 的投放素材与落地页不匹配(素材讲促销、落地页是新品页)。"""
    materials = ["满300减50大促", "新人首单立减", "9.9元秒杀", "会员专享价", "以旧换新补贴"]
    landings = ["促销专题页", "爆款清仓页", "会员专享页", "大促会场页"]
    rows = []
    for i in range(200):
        channel = RNG.choices(["A", "B", "C"], weights=[0.4, 0.35, 0.25])[0]
        if channel == "A":
            material = RNG.choice(materials)  # 促销类素材
            landing = RNG.choice(["新品首发页", "新品试用页", "品牌故事页"])  # 落地页却是新品页
        else:
            material = RNG.choice(["爆款直降", "限时折扣", "满减券"] + materials)
            landing = RNG.choice(landings)
        rows.append({
            "日期": f"2026-08-{RNG.randint(1, 28):02d}",
            "渠道": channel,
            "投放素材": material,
            "落地页": landing,
            "曝光量": RNG.randint(5000, 30000),
            "点击量": RNG.randint(100, 1500),
            "消耗金额(元)": round(RNG.uniform(2000, 15000), 2),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(OUT / "渠道投放明细.xlsx", index=False)
    print(f"已生成 {OUT / '渠道投放明细.xlsx'} ({len(rows)} 行)")


if __name__ == "__main__":
    gen_competitor_csv()
    gen_channel_ads_xlsx()
