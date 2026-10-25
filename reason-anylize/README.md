# 经营归因分析系统

面向经营分析场景的**多轮归因分析系统**: 围绕一个业务问题持续追问、上传补充证据、实时观察分析过程(状态/步骤/工具执行),获得阶段性结论与最终分析报告,并支持结果导出与重新下载。

## 架构

| 服务 | 端口 | 技术栈 | 职责 |
|---|---|---|---|
| `frontend/` | 5173 | React 18 + Vite + TS + Ant Design 5 | 聊天工作台、实时任务区、结果区、附件侧栏、管理端 |
| `backend/` | 8000 | Python 3.11 + FastAPI + SQLAlchemy | 会话/消息/附件/任务/结果、WebSocket 实时通道、LLM 工具调用循环(AgentLoop)、配置热更新 |
| `auth-service/` | 8001 | FastAPI(独立进程) | mock OAuth2 授权中心(授权码模式),内置测试账号 |

```
浏览器 ──> 前端(5173) ──/api,/auth 代理──> 后端(8000) ──> 认证中心(8001)
                │                                │
                └──── WS /api/chat/ws/chat ──────┘        └──> LLM(OpenAI 兼容协议: DeepSeek/Qwen/GLM)
```

分析引擎: LLM function-calling 手动循环 + 5 类工具(只读 SQL 查询、workspace 文件读写、附件文本检索、沙箱命令执行、结果文件生成),六部分结构化结果经严格 JSON Schema 校验落库,长对话自动触发上下文摘要压缩。

## 快速启动

环境要求: [uv](https://docs.astral.sh/uv/)(Python 管理)、Node.js ≥ 18。

```powershell
# 1. 一键启动(Windows): 生成演示数据 → 起认证中心 → 起后端 → 起前端
scripts\start_all.ps1

# 或分步(Linux/macOS 用 scripts/start_all.sh):
uv sync --project backend
uv run --project backend python scripts/seed_data.py          # 种子数据(两场景,确定性)
uv run --project backend python scripts/demo_assets_generator.py  # 演示上传素材
# 终端1: cd auth-service && uv run python run.py
# 终端2: cd backend && uv run python run.py
# 终端3: cd frontend && npm install && npm run dev
```

浏览器访问 **http://localhost:5173**,点击「授权登录」,使用测试账号:

| 账号 | 密码 | 角色 |
|---|---|---|
| analyst1 | analyst123 | 分析用户 |
| admin1 | admin123 | 系统管理员 |

## 配置真实 LLM(可选)

系统不配 API Key 也能跑通**自动化演示**(脚本化 Mock,见下)。接入真实模型:

1. 管理员登录 → 管理端「系统配置」: 填 `llm.api_key`,按需改 `llm.base_url` / `llm.model`(默认 DeepSeek);
2. 「配置重载」即时生效(无需重启)。也可设环境变量 `LLM_API_KEY`。

## 演示

1. **自动化全链路演示(无需 API Key)** —— 两场景 13 轮真实数据 + 真实工具执行:
   ```powershell
   uv run --project backend python backend/demo_scripts/run_demo_conversation.py
   ```
2. **人工演示脚本(配真实 LLM)**:
   - [演示脚本一 · 商品目录优化(7 轮)](docs/demo/01-商品目录优化-演示脚本.md)
   - [演示脚本二 · 客户行为分析(6 轮)](docs/demo/02-客户行为分析-演示脚本.md)

## 文档

- [接口说明 API.md](docs/API.md) —— 全部 REST 接口(含管理端与配置项说明)
- [WebSocket 实时协议 WS_PROTOCOL.md](docs/WS_PROTOCOL.md) —— 8 类实时消息、重连与回放约定
- [部署说明 DEPLOY.md](docs/DEPLOY.md) —— MySQL 切换、生产部署与安全建议

## 测试

```powershell
cd backend && uv run pytest   # 31 用例: 认证链路/会话级联/附件解析/工具安全/WS 全链路/取消竞态(全 mock,不打真实 API)
uv run --project backend python scripts/check_schema.py   # models.py ↔ init_mysql.sql 一致性校验
```

## 目录结构

```
├── backend/          # FastAPI 主服务(app/api|core|engine|services|tools|workers, tests, demo_scripts)
├── auth-service/     # mock OAuth2 授权中心(登录页内置测试账号一键填充)
├── frontend/         # React 聊天工作台
├── scripts/          # seed_data.py / demo_assets_generator.py / init_mysql.sql / check_schema.py / start_all.*
└── docs/             # API 契约、WS 协议、部署说明、两场景演示脚本与素材
```
