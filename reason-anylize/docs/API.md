# 接口说明(API.md)

后端服务 `http://localhost:8000`(接口文档: `/docs`)。开发模式下前端经 Vite proxy 将 `/api`、`/auth` 转发至后端,前端代码中统一使用相对路径。

**约定**

- 除登录相关接口外均需登录态: 浏览器 Cookie `session_token`(HttpOnly, 由授权回调写入)。
- 错误响应统一为 `{"detail": "<错误信息>"}`,状态码 400/401/404/500。
- 时间字段为 ISO 格式字符串。
- 管理员接口(`/api/admin/*`)要求当前用户 role=admin。

## 1. 认证

### GET /auth/login
发起授权登录。生成 state 存 Cookie(`oauth_state`),302 跳转认证中心(8001)授权页。

### GET /auth/callback
处理授权回调(认证中心 302 回跳)。校验 state → 换 access_token → 取用户信息 → upsert `users` 表 → 签发 `session_token` Cookie → 302 跳转前端 `/auth/callback`。

### GET /api/auth/me
当前登录用户。响应:
```json
{"user_id": 1, "username": "analyst1", "display_name": "分析用户", "role": "analyst", "status": "active"}
```

### POST /api/auth/logout
清除 `session_token` Cookie。

## 2. 会话

### POST /api/chat/create
请求: `{"title": "会话标题"}`(可空,默认"新会话")
响应: `{"conversation_id": 1, "title": "...", "status": "active", "last_message_at": null}`

### POST /api/chat/delete
请求: `{"conversation_ids": [1, 2]}`
响应: `{"deleted": 2}`
级联删除会话下消息/附件记录/任务/结果/上下文摘要,以及磁盘 `uploads/`、`exports/`、`workspace/` 三目录。

### POST /api/chat/update
请求: `{"conversation_id": 1, "title": "新标题", "status": "archived"}`
- 仅传 title → 重命名;status=archived → 归档;status=active → 取消归档。
响应: 会话视图(同 create)。

### GET /api/chat/ls
响应: `{"conversations": [{"conversation_id": 1, "title": "...", "status": "active", "last_message_at": "..."}]}`(按最近消息倒序)

### GET /api/chat/ls/{conversation_id}
响应:
```json
{"messages": [
  {"message_id": 1, "role": "user", "content": "...", "message_type": "text",
   "tool_name": null, "tool_status": null, "seq_no": 1,
   "attachments": [{"attachment_id": 1, "file_name": "a.csv", "file_type": "csv", "file_size": 123, "parse_status": "parsed"}],
   "created_at": "..."}
]}
```

### POST /api/chat/ws-token
签发一次性 WebSocket 连接令牌(60s 过期)。响应: `{"websocket_token": "...", "expires_in": 60}`

## 3. 附件

### POST /api/attachment/upload
multipart/form-data: `conversation_id`(int)+ `file`(文件,≤20MB)
响应: `{"attachment_id": 1, "file_name": "a.csv", "file_path": "uploads/1/1/xxx_a.csv"}`
上传后自动进入后台解析管线,`parse_status` 流转 pending → parsing → parsed / failed,经 WS `attachment_parsed` 事件或轮询 `/api/attachment/ls` 感知。

### POST /api/attachment/delete
请求: `{"attachment_id": 1}` → `{"deleted": 1}`

### GET /api/attachment/get?attachment_id=1
下载附件原始文件(FileResponse)。

### GET /api/attachment/ls?conversation_id=1
响应: `{"attachments": [{"attachment_id": 1, "conversation_id": 1, "message_id": 2, "file_name": "...", "file_type": "csv", "file_size": 123, "parse_status": "parsed", "created_at": "..."}]}`

## 4. 任务

### GET /api/tasks/{task_id}
响应:
```json
{"task_id": 1, "conversation_id": 1, "task_status": "running", "current_step": "tool_execution:db_query",
 "input_text": "...", "started_at": "...", "finished_at": null, "error_message": null}
```

### GET /api/tasks/{task_id}/events
断线重连后的任务事件回放(最多 200 条,与 WS 消息同构)。响应: `{"events": [{"type": "message_start", ...}, ...]}`

### POST /api/tasks/{task_id}/cancel
请求取消(协作式)。响应: `{"task_id": 1, "requested": true}`
任务已终态时: `{"requested": false, "message": "任务已处于终态,无需取消"}`

## 5. 分析结果

### GET /api/results/{task_id}
六部分结构化结果(需求文档第 11 节):
```json
{
  "result_id": 1, "task_id": 1,
  "problem_definition": "为什么厨房小家电转化率偏低",
  "key_metrics": [{"metric_name": "点击下单转化率", "metric_value": "1.01%", "metric_unit": "%", "metric_period": "近60天"}],
  "evidence_list": [{"source_type": "database", "source_name": "scn1_clicks", "evidence_text": "...", "related_metric": "...", "confidence": "high"}],
  "conclusion_text": "...",
  "missing_data_text": "...",
  "next_action_text": ["...", "..."] ,
  "result_markdown": "...",
  "result_file_path": "exports/1/1/1_analysis_result.md",
  "created_at": "..."
}
```
任务尚无结果时 404。

### GET /api/results/{task_id}/export?format=md|html|json
导出结果文件(Content-Disposition 附件下载)。

### GET /api/results/{task_id}/download
下载系统生成的分析报告 markdown 文件(`result_file_path`)。
### GET /api/results/{task_id}/download?file={文件名}
下载 `result_file` 工具生成的用户结果文件(仅限本会话导出目录内)。

## 6. 管理端(role=admin)

### POST /api/admin/reload
配置热更新: 从 `system_configs` 表重载到内存。响应: `{"status": "ok", "message": "配置已重载,共 N 项生效"}`

### GET /api/admin/configs
全部配置项: `{"configs": [{"config_key": "llm.model", "config_value": "deepseek-chat", "config_group": "llm", "updated_at": "..."}]}`

### PUT /api/admin/configs
请求: `{"key": "llm.model", "value": "qwen-plus"}` → 立即生效(无需 reload)

### GET /api/admin/logs?lines=200
后端运行日志尾部(backend/logs/app.log)。

### GET /api/admin/datasources
`{"current": {"type": "sqlite", "conn": "..."}, "database_url": "..."}`

### POST /api/admin/datasources/test
请求: `{"db_type": "sqlite|mysql", "conn": "..."}` → `{"ok": true, "message": "连接成功"}`
仅测试连通性,不切换(切换需改 .env DATABASE_URL 重启)。

### GET /api/admin/features / PUT /api/admin/features
功能开关查看/更新(key 形如 `feature.db_query`,value `on|off`)。关闭的工具不再注入 LLM 工具列表且执行被拒。

## 7. system_configs 默认配置

| 组 | 键 | 默认值 | 说明 |
|---|---|---|---|
| llm | llm.provider | openai-compatible | `openai-compatible` / `mock` |
| llm | llm.base_url | https://api.deepseek.com/v1 | OpenAI 兼容协议地址(Qwen/GLM 可改) |
| llm | llm.api_key | (空) | 为空时回退环境变量 LLM_API_KEY |
| llm | llm.model | deepseek-chat | 模型名 |
| llm | llm.temperature | 0.2 | |
| llm | llm.max_tokens | 4096 | |
| llm | llm.timeout | 120 | 秒 |
| feature | feature.db_query | on | 只读 SQL 查询 |
| feature | feature.file_ops | on | workspace 文件读写 |
| feature | feature.text_search | on | 附件/文件检索 |
| feature | feature.command_exec | off | 沙箱命令执行(演示沙箱能力时开启) |
| feature | feature.result_file | on | 结果文件生成 |
| analysis | analysis.max_tool_rounds | 8 | 单任务工具调用轮数上限 |
| analysis | analysis.history_window | 20 | 注入上下文的历史消息条数 |
| analysis | analysis.summary_trigger_msgs | 30 | 触发摘要压缩的消息数 |
| analysis | analysis.summary_keep_recent | 12 | 压缩时保留的最近消息数 |
| analysis | analysis.attachment_excerpt_chars | 2000 | 附件摘录字符数 |
| analysis | analysis.task_timeout | 600 | 任务超时(秒) |
| datasource | datasource.main.type | sqlite | |
| sandbox | sandbox.type | process | `process` / `docker` |
