"""Mock 审批系统静态数据:4 张审批单。

- HT-2026-001 软件技术服务合同(文本 PDF,预期中风险)
- HT-2026-002 设备采购合同(扫描件 JPG,预期高风险,走 OCR 降级)
- HT-2026-003 办公家具采购合同(无附件,blocked 演示,重试时补传)
- HT-2026-004 装修工程合同(空白 PDF,内容为空 blocked 演示)
"""
from app.config import PROJECT_ROOT

SAMPLE_DIR = PROJECT_ROOT / "samples" / "contracts"

MOCK_APPROVALS = [
    {
        "instance_id": "HT-2026-001",
        "title": "软件技术服务合同审批",
        "applicant": "张伟",
        "apply_time": "2026-02-20T09:30:00",
        "form_data": {
            "合同类型": "软件技术服务",
            "申请部门": "信息中心",
            "预算金额": "128,000 元",
            "我方主体": "北京某科技发展有限公司",
            "对方主体": "上海某软件服务有限公司",
            "审批事由": "2026 年度企业管理软件开发及实施服务采购",
        },
        "attachments": [
            {
                "attachment_id": "ATT-2026-001-1",
                "file_name": "软件技术服务合同.pdf",
                "file_type": "pdf",
                "local_file": "samples/contracts/software_service_contract.pdf",
            }
        ],
    },
    {
        "instance_id": "HT-2026-002",
        "title": "自动化生产线设备采购合同审批",
        "applicant": "李娜",
        "apply_time": "2026-03-10T14:20:00",
        "form_data": {
            "合同类型": "设备采购",
            "申请部门": "生产制造部",
            "预算金额": "500,000 元",
            "我方主体": "北京某制造有限公司",
            "对方主体": "深圳某设备有限公司",
            "审批事由": "自动化生产线设备采购(合同为扫描件)",
        },
        "attachments": [
            {
                "attachment_id": "ATT-2026-002-1",
                "file_name": "设备采购合同(扫描件).jpg",
                "file_type": "jpg",
                "local_file": "samples/contracts/equipment_purchase_contract.jpg",
                "ocr_json": "samples/contracts/equipment_purchase_contract.ocr.json",
            }
        ],
    },
    {
        "instance_id": "HT-2026-003",
        "title": "办公家具采购合同审批",
        "applicant": "王强",
        "apply_time": "2026-03-15T10:00:00",
        "form_data": {
            "合同类型": "办公用品采购",
            "申请部门": "行政部",
            "预算金额": "86,000 元",
            "我方主体": "北京某科技发展有限公司",
            "对方主体": "北京某家具有限公司",
            "审批事由": "新办公区家具采购(附件缺失,待补传)",
        },
        "attachments": [],
    },
    {
        "instance_id": "HT-2026-004",
        "title": "装修工程合同审批",
        "applicant": "赵敏",
        "apply_time": "2026-03-18T16:45:00",
        "form_data": {
            "合同类型": "装修工程",
            "申请部门": "行政部",
            "预算金额": "260,000 元",
            "我方主体": "北京某科技发展有限公司",
            "对方主体": "北京某装饰工程有限公司",
            "审批事由": "办公区装修改造工程",
        },
        "attachments": [
            {
                "attachment_id": "ATT-2026-004-1",
                "file_name": "装修工程合同.pdf",
                "file_type": "pdf",
                "local_file": "samples/contracts/empty_contract.pdf",
            }
        ],
    },
]
