# 合同审批自动审查系统

面向企业合同审批场景的自动审查系统:自动拉取待办审批单、下载合同附件、解析合同(文本 PDF + 扫描件 OCR)、执行规则审查、生成风险审查意见并写回审批评论区。**自动审查意见仅供法务参考,不直接代替人工审批。**

- 后端:Python 3.12 + FastAPI + SQLAlchemy(SQLite 默认,可切 MySQL)
- 审批接入:内置 Mock 审批服务,接口层抽象,预留飞书适配器(配置切换)
- 调用端:内嵌 Web 界面(5 个业务模块 + 管理页)+ CLI 一键闭环演示脚本

## 目录结构

```
app/
  tools/        7 个工具(唯一业务入口,统一 ToolResult 返回)
  services/     拉取/附件/解析/规则/回写/日志 六模块 + 状态机
  adapters/     审批系统适配器(mock | feishu 骨架)
  rules/        五种 match_mode 匹配器 + 风险汇总算法
  api/          REST 路由(/api/tools/* 7 工具、任务/重试、规则维护、日志)
  web/          Jinja2 页面 + 原生 JS(无构建)
scripts/
  init_db.py            建表 + 可选种子规则
  generate_samples.py   生成 4 份示例合同
  demo_closed_loop.py   一键闭环演示
samples/contracts/      示例合同(文本 PDF / 扫描件 JPG+预识别文本 / 空白 PDF)
config/settings.yaml    运行配置(适配器/OCR/DB/回写故障注入)
```

## 快速开始

```bash
# 1. 安装依赖(项目 uv.toml 已配置官方 PyPI 源)
uv sync

# 2. 初始化数据库 + 灌入 12 条种子规则
uv run python -m scripts.init_db --seed

# 3. 生成示例合同(文本 PDF、扫描件 JPG、空白 PDF)
uv run python -m scripts.generate_samples

# 4. 一键闭环演示(拉取→下载→解析→审查→保存→回写 + blocked 重试 + 回写失败重试 + 去重验证)
uv run python -m scripts.demo_closed_loop --fresh

# 5. 启动 Web 界面
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
# 浏览器打开 http://127.0.0.1:8010
```

> 端口 8010 为默认配置(8000 常被占用,可在 config/settings.yaml 修改)。运行单元测试:`uv run pytest`。

## 七个工具说明

所有工具返回统一结构 `{success, data, error}`,Web 与 CLI 均只调用工具层。REST 端点与工具同名,POST 请求体即工具参数(见 app/api/routes/tools.py)。

| 工具 | 参数 | 说明 |
|---|---|---|
| `list_pending_contract_approvals` | `limit` | 拉取待处理审批单(编号/标题/申请人/申请时间/附件数),按 `approval_code` 唯一键去重 upsert,返回新建/更新计数 |
| `get_contract_approval` | `instance_id` | 审批详情:审批信息、表单数据、附件信息、当前处理状态(本地任务状态) |
| `download_contract_attachment` | `instance_id, attachment_id, file_name` | 下载附件落盘 `data/attachments/{审批编号}/`,返回本地路径/md5/大小/附件记录 id;失败任务进 blocked |
| `parse_contract_document` | `document_id` | 解析文档(参数=附件记录 id):PDF 用 pypdf 逐页提取,图片走 OCR(降级预识别文本或 PaddleOCR);输出 8 基本信息字段 + 8 类条款,每字段含原文片段/定位/提取状态;失败落 parse_error + blocked |
| `run_contract_rules` | `case_id` | 执行规则审查(参数=任务主键 id):5 种 match_mode 匹配 → 命中落库(重跑先删后插)→ 输出总风险等级(低/中/高)、命中列表(规则/等级/证据/位置/建议)、中文摘要、审批关注点、回写文本 |
| `save_review_result` | `case_id, overall_risk_level, summary_text, focus_points_json, comment_text` | 保存审查结果(校验等级与 JSON),任务 → done |
| `write_approval_comment` | `instance_id, review_id` | 将审查意见写回审批评论区(review_id = 审查结果 id),记录 comment_logs 时间线,失败可重试 |

## 状态机

```
pending → parsing → reviewing → done
   ↓         ↓          ↓
   └──── blocked ── 人工重试 → parsing | reviewing
```

- 回写状态独立流转:`not_written → writing → success / failed`(failed 可重试)
- blocked 触发点:附件缺失、附件下载失败、图片无法识别(OCR 不可用/结果为空)、文档内容为空、解析异常、规则引擎异常、审批接口调用失败
- 重复拉取只更新展示字段,**不重置 done/blocked 状态**

## 审查规则

- 规则字段:`rule_code / rule_name / risk_level / rule_status / match_mode / match_text(JSON) / suggestion_text`
- 5 种 match_mode:`regex`(支持取反)、`keyword`、`field_missing`(支持多字段 any/all)、`clause_missing`(支持 vague_pattern 判"存在但含糊")、`value_compare`
- 种子规则 12 条:预付款比例(>30%)、付款周期(>45天)、自动续约、违约责任不对等、管辖地不利、主体/金额/保密/数据/知识产权/验收标准缺失、生效到期日期缺失
- 风险汇总(保守原则):高命中≥1 → 高;中命中≥3 → 高;中 1~2 → 中;仅低 → 低
- 规则可在管理页维护(启停/编辑/新增),停用后重新审查即生效

## 演示场景对照(scripts/demo_closed_loop.py)

| 审批单 | 附件 | 场景 | 预期结果 |
|---|---|---|---|
| HT-2026-001 | 文本 PDF | 全链路,埋自动续约+管辖地风险 | 总风险 **中**,回写成功 |
| HT-2026-002 | 扫描件 JPG | 降级 OCR + 中文大写金额(伍拾万元整→500000) | 总风险 **高**,回写成功 |
| HT-2026-003 | 无附件 | 附件缺失 blocked → 模拟补传 → 人工重试 → done | 总风险 **低** |
| HT-2026-004 | 空白 PDF | 文档内容为空 → blocked(保留演示) | blocked |
| --fail-write | 故障注入 | 回写失败(writing→failed)→ 恢复后重试 → success | comment_logs 完整时间线 |

```bash
uv run python -m scripts.demo_closed_loop --only HT-2026-001      # 仅演示指定单
uv run python -m scripts.demo_closed_loop --fail-write HT-2026-001  # 追加回写失败重试
uv run python -m scripts.demo_closed_loop --strict                # CI 验收:存在 blocked/failed 退出码 1
```

## 扩展指引

**切换 MySQL**:改 `config/settings.yaml` 的 `db.url` 为 `mysql+pymysql://user:pass@host:3306/contract_approval?charset=utf8mb4`,依赖加 `pymysql`,`init_db.py` 建表脚本不变。

**真实 OCR(PaddleOCR)**:`uv sync --group ocr` 安装,`config/settings.yaml` 设 `ocr.backend: paddle`。演示默认用 fallback 降级 OCR(读取与扫描件同名的 `.ocr.json` 预识别文本)。

**对接飞书审批**:`config/settings.yaml` 设 `approval.adapter: feishu` 并配置 app_id/app_secret,实现 `app/adapters/feishu_adapter.py` 中四个方法(每个方法 docstring 标注了对应飞书审批 v3 API),业务代码零改动。

**配置项**:`config/settings.yaml` 支持 adapter 开关、Mock 回写故障注入(`approval.mock.fail_write_for`)、OCR 后端、DB URL、服务端口;环境变量 `APPROVAL_ADAPTER / OCR_BACKEND / DB_URL` 可覆盖。

## 验收标准对照(CLAUDE.md 第 12 节)

1. ✅ 拉取待办 + 按唯一业务标识去重 —— 工具1 + 演示步骤 7(重复拉取 0 新建)
2. ✅ 附件下载 + 附件记录保存 —— 工具3,落盘 + md5/大小/下载状态
3. ✅ 解析文档和图片扫描件,提取主要字段 —— 工具4(8 字段 + 8 条款,含原文片段/定位/提取状态)
4. ✅ 规则审查返回命中证据和风险等级 —— 工具5(12 规则 5 模式,证据含位置)
5. ✅ 保存审查结果并写回评论区 —— 工具6/7(comment_logs 时间线,Mock 收到的评论原文可在 Web 输出页查看)
6. ✅ 异常任务阻塞 + 重试 —— 附件缺失/OCR 失败/内容为空/接口失败均 blocked,人工重试恢复
7. ✅ 完整闭环演示 —— CLI 一键演示 + Web 五模块页面
