# 部署说明(DEPLOY.md)

## 一、开发/演示环境(默认)

- 数据库: SQLite `backend/data/app.db`(WAL 模式,零配置);文件存储 `backend/storage/{uploads,exports,workspace}/`
- 三服务按 [README](../README.md) 一键启动;`scripts/start_all.ps1` 会先跑种子数据(幂等,可重复执行)
- 前端经 Vite proxy 与后端同源,cookie 天然生效,无需处理跨域

## 二、切换 MySQL(生产)

1. 初始化库表:
   ```bash
   mysql -u root -p -e "CREATE DATABASE reason_analyze DEFAULT CHARSET utf8mb4"
   mysql -u root -p reason_analyze < scripts/init_mysql.sql
   ```
2. 种子数据(与 SQLite 同一脚本,双 dialect):
   ```bash
   uv run --project backend python scripts/seed_data.py --db-url "mysql+pymysql://user:pass@127.0.0.1:3306/reason_analyze?charset=utf8mb4"
   ```
3. `backend/.env`:
   ```
   DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/reason_analyze?charset=utf8mb4
   ```
4. 一致性校验: `uv run --project backend python scripts/check_schema.py`(models.py 与 DDL 双轨防漂移)

注意: `db_query` 工具走只读连接,MySQL 生产建议为分析账号单独配置只读权限;`datasource.main.*` 配置项目前仅作展示与连接测试,真实数据源切换以 `DATABASE_URL` 为准(重启生效)。

## 三、生产部署建议

1. **反向代理同域**: `/`(前端构建产物)、`/api`、`/auth` 由同一域名反代到后端,保证登录 Cookie 与 WS 同源;WS 路径 `/api/chat/ws/chat` 需开启 Upgrade 支持(nginx 示例):
   ```nginx
   location /api/chat/ws/chat {
       proxy_pass http://127.0.0.1:8000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_read_timeout 3600s;
   }
   ```
2. **前端构建**: `cd frontend && npm run build`,产物 `dist/` 由 nginx 托管;`vite.config.ts` 的 proxy 仅用于开发。
3. **认证中心**: 演示用 mock 服务仅适合内网/演示;生产对接真实 IdP 时替换 `backend/app/api/auth.py` 中 `/oauth/token`、`/oauth/userinfo` 的地址与字段映射即可(其余链路不变)。`AUTH_CLIENTS` / `AUTH_ALLOWED_REDIRECT_PREFIXES` 环境变量控制 mock 中心的客户端与回调白名单。
4. **沙箱命令执行**: `feature.command_exec` 默认关闭;生产开启时建议 `sandbox.type=docker`(容器 `--network none --memory 512m --cpus 1 --read-only`),并确保后端所在主机已装 Docker;演示环境 `process` 沙箱仅作功能展示,不建议用于不可信输入。
5. **密钥与配置**: `JWT_SECRET` 必须替换为随机长密钥;`LLM_API_KEY` 建议通过环境变量注入;`system_configs` 中 `llm.api_key` 仅推荐在受控内网使用(管理端可见)。
6. **单进程限制**: 应用内单任务锁基于进程内事件 + 数据库存在性检查;多 worker 部署时 SQLite 不支持并发写,请使用 MySQL,并可叠加 `GET_LOCK` 强化(现未启用,并发窗口极小)。
7. **备份**: 数据 = `DATABASE_URL` 指向的库 + `STORAGE_ROOT` 三目录;会话删除是级联物理删除,建议定期备份。

## 四、端口与地址速查

| 项 | 默认值 | 环境变量 |
|---|---|---|
| 后端 | http://localhost:8000 | - |
| 认证中心 | http://localhost:8001 | `AUTH_SERVICE_BASE_URL`(后端侧) |
| 前端 | http://localhost:5173 | `FRONTEND_URL`(后端回调跳转目标) |
| 后端对外地址 | http://localhost:8000 | `BACKEND_PUBLIC_URL`(OAuth redirect_uri) |
| 数据库 | sqlite:///./data/app.db | `DATABASE_URL` |
| 存储根 | ./storage | `STORAGE_ROOT` |
| JWT 密钥 | dev-secret-change-me(必须改) | `JWT_SECRET` |
