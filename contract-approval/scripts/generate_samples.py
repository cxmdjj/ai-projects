"""示例合同生成脚本(确定性生成,可重复运行)。

产出:
  software_service_contract.pdf      文本 PDF,埋 2 个中风险点(自动续约 + 管辖地)→ 预期总风险 中
  equipment_purchase_contract.jpg    扫描件图片 + .ocr.json 预识别文本,埋高风险点 → 预期总风险 高
  office_furniture_contract.pdf      正常合同(blocked 重试演示补传用)→ 预期总风险 低
  empty_contract.pdf                 空白合同(内容为空 blocked 演示)

用法: python -m scripts.generate_samples
"""
import json
from pathlib import Path

from app.config import PROJECT_ROOT

OUT_DIR = PROJECT_ROOT / "samples" / "contracts"

CONTRACT_A = """软件技术服务合同

合同编号:HT-2026-001-A

甲方(委托方):北京某科技发展有限公司
乙方(受托方):上海某软件服务有限公司

第一条 服务内容与期限
乙方为甲方提供企业管理软件开发及实施服务。本合同自 2026年3月1日 生效,至 2027年2月28日 到期。

第二条 合同金额
本合同总金额为人民币 128,000 元(大写:壹拾贰万捌仟元整)。

第三条 付款条款
合同签订后 10 日内,甲方向乙方支付合同总价 20% 的预付款;项目验收合格后 30 日内,甲方支付剩余 80% 的合同款。

第四条 交付条款
乙方应在合同生效后 90 日内完成系统开发并交付部署。

第五条 验收条款
系统上线试运行 30 日且缺陷率低于 1% 的,视为验收合格。

第六条 违约条款
任何一方违反本合同约定的,应向守约方支付合同总价 10% 的违约金,并赔偿由此造成的损失。

第七条 合同续期
本合同期满前 30 日,双方未书面提出异议的,本合同自动续期一年。

第八条 保密条款
双方对履行本合同过程中知悉的对方商业秘密负有保密义务,未经对方书面同意不得向第三方披露。

第九条 数据条款
乙方处理甲方数据应遵守相关法律法规,未经甲方书面授权不得将数据用于本合同目的之外的其他用途。

第十条 知识产权条款
项目开发成果的知识产权归甲方所有,乙方享有署名权。

第十一条 争议解决
因本合同引起的争议,双方应友好协商解决;协商不成的,任何一方均有权提交乙方所在地人民法院管辖。

甲方(盖章):北京某科技发展有限公司
乙方(盖章):上海某软件服务有限公司
签订日期:2026年2月20日"""

CONTRACT_B = """设备采购合同

合同编号:HT-2026-002-B

甲方(买方):北京某制造有限公司
乙方(卖方):深圳某设备有限公司

第一条 合同标的与期限
甲方向乙方采购自动化生产线设备一套,合同总金额为人民币伍拾万元整。本合同自 2026年4月1日 生效,至 2027年3月31日 止。

第二条 付款条款
合同签订后 10 日内,甲方向乙方支付预付款,预付款比例为合同总价的 50%;设备验收合格后 90 日内,甲方支付剩余款项。

第三条 交付与验收条款
乙方应于合同生效后 60 日内完成设备交付。设备安装调试完毕并连续稳定运行 72 小时,且关键指标检测合格率不低于 98% 的,视为验收合格。

第四条 违约条款
甲方逾期付款的,每逾期一日按逾期金额的万分之五向乙方支付违约金。

第五条 保密条款
双方应对履行本合同过程中知悉的对方商业秘密和技术秘密承担保密义务,保密期限为合同终止后五年。

第六条 争议解决
因本合同引起的争议,双方应友好协商解决;协商不成的,提交甲方所在地人民法院管辖。

甲方(盖章):北京某制造有限公司
乙方(盖章):深圳某设备有限公司
签订日期:2026年3月15日"""

CONTRACT_C = """办公家具采购合同

合同编号:HT-2026-003-C

甲方(买方):北京某科技发展有限公司
乙方(卖方):北京某家具有限公司

第一条 合同标的与期限
甲方向乙方采购办公家具一批,合同总金额为人民币 86,000 元(大写:捌万陆仟元整)。本合同自 2026年4月1日 生效,至 2026年6月30日 到期。

第二条 付款条款
合同签订后 5 日内,甲方向乙方支付合同总价 10% 的预付款;全部家具验收合格后 20 日内,甲方支付剩余 90% 的合同款。

第三条 交付条款
乙方应于合同生效后 30 日内完成全部家具交付与安装。

第四条 验收条款
家具外观无破损、安装牢固,数量与订单一致,且符合国家环保标准的,视为验收合格。

第五条 违约条款
任何一方违反本合同约定的,应向守约方支付合同总价 10% 的违约金;给守约方造成损失的,应赔偿全部损失。

第六条 保密条款
双方对履行本合同过程中知悉的对方商业秘密负有保密义务。

第七条 数据条款
双方在履行本合同过程中涉及的个人信息,应依法处理,不得泄露。

第八条 知识产权条款
本合同履行过程中形成的设计方案等成果的知识产权归甲方所有。

第九条 争议解决
因本合同引起的争议,双方应友好协商解决;协商不成的,提交甲方所在地人民法院管辖。

甲方(盖章):北京某科技发展有限公司
乙方(盖章):北京某家具有限公司
签订日期:2026年3月20日"""

# 空合同:仅标题行(演示"文档内容为空" → blocked)
CONTRACT_D = """装修工程合同"""


def _write_pdf(path: Path, lines: list[str]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    title_style = ParagraphStyle("title", fontName="STSong-Light", fontSize=16, leading=24, spaceAfter=12)
    body_style = ParagraphStyle("body", fontName="STSong-Light", fontSize=11, leading=20)
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    story = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        story.append(Paragraph(line.strip(), title_style if i == 0 else body_style))
    doc.build(story)


def _write_image(path: Path, lines: list[str]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"):
        try:
            font = ImageFont.truetype(fp, 32)
            break
        except Exception:
            continue
    if font is None:
        raise SystemExit("未找到可用中文字体(尝试了 msyh.ttc / simhei.ttf / simsun.ttc),无法生成扫描件示例")

    img = Image.new("RGB", (1500, 62 * len(lines) + 160), "white")
    draw = ImageDraw.Draw(img)
    draw.text((70, 50), lines[0], fill="black", font=font)
    y = 140
    for line in lines[1:]:
        if line.strip():
            draw.text((70, y), line, fill="black", font=font)
        y += 62
    img.save(path, quality=92)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_pdf(OUT_DIR / "software_service_contract.pdf", CONTRACT_A.splitlines())
    _write_image(OUT_DIR / "equipment_purchase_contract.jpg", CONTRACT_B.splitlines())
    (OUT_DIR / "equipment_purchase_contract.ocr.json").write_text(
        json.dumps({"text": CONTRACT_B, "engine": "pre-recognized"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_pdf(OUT_DIR / "office_furniture_contract.pdf", CONTRACT_C.splitlines())
    _write_pdf(OUT_DIR / "empty_contract.pdf", CONTRACT_D.splitlines())
    print("示例合同生成完成:")
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
