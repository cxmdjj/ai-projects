# WebSocket 实时协议(WS_PROTOCOL.md)

## 连接

```
ws://<backend>/api/chat/ws/chat?websocket_token=<token>&conversation_id=<id>
```

1. 先 `POST /api/chat/ws-token`(需登录 Cookie)获取一次性 `websocket_token`(60s 过期);
2. 用 token + `conversation_id` 建立连接,服务端校验 token 未过期未消费、会话归属当前用户,**消费 token 后 accept**;
3. token 一次性: 断线重连必须重新申请 token;鉴权失败服务端以 4401/4403 关闭连接;
4. 客户端可同时开多个连接(同一会话均可收到广播);任务执行与连接解耦,断线不终止任务。

## 消息格式

统一 JSON 文本帧: `{"type": "<类型>", ...字段}`。

## 客户端 → 服务端

| type | 字段 | 说明 |
|---|---|---|
| `ping` | - | 心跳,服务端回 `pong`;建议 30s 一次,10s 无 `pong` 判死重连 |
| `chat_message` | `content`(string),`attachment_ids`(int[],可选) | 发送分析问题;一条消息对应一个分析任务;同一会话同时只允许一个运行中任务,冲突时收到 error 消息 |
| `cancel_task` | `task_id`(int) | 取消运行中的任务(协作式,取消延迟 ≤ 一个流式块) |

## 服务端 → 客户端(需求文档第 10 节 8 类)

| type | 字段 | 说明 |
|---|---|---|
| `message_start` | `task_id`, `conversation_id` | 本轮分析开始 |
| `message_delta` | `task_id`, `delta_text` | 模型增量文本(流式渲染) |
| `tool_start` | `task_id`, `tool_name` | 工具开始执行(db_query/file_read/file_write/file_list/text_search/command_exec/result_file) |
| `tool_finish` | `task_id`, `tool_name`, `tool_result_summary` | 工具执行完成(摘要 ≤500 字) |
| `task_status` | `task_id`, `task_status`, `current_step` | 状态变化;task_status ∈ queued/running/success/failed/cancelled;current_step 示例: `context_assembly`、`llm_reasoning:N`、`tool_execution:db_query`、`result_generation`、`result_finalize`、`summary_compression`、`done` |
| `result_ready` | `task_id`, `result_id` | 六部分结构化结果已生成,可调 `GET /api/results/{task_id}` |
| `error` | `task_id`(可为 null),`error_message` | 本轮分析失败(含单任务锁冲突) |
| `done` | `task_id`, `finished_at` | 本轮分析结束(success/failed/cancelled 后都会发) |

扩展事件:

| type | 字段 | 说明 |
|---|---|---|
| `attachment_parsed` | `attachment_id`, `parse_status` | 附件后台解析完成(parsed/failed),用于刷新附件侧栏状态 |
| `pong` | - | 心跳应答 |

## 典型一轮时序

```
client → chat_message
server → message_start{task_id}
server → task_status{queued}
server → task_status{running, context_assembly}
server → task_status{running, llm_reasoning:1}
server → message_delta × N(模型流式文本)
server → tool_start{db_query} → task_status{running, tool_execution:db_query} → tool_finish{db_query, summary}
server → message_delta × N
server → task_status{running, result_generation}
server → result_ready{task_id, result_id}   (客户端 GET /api/results/{task_id} 渲染六部分)
server → task_status{running, summary_compression}
server → task_status{success, done}
server → done{task_id, finished_at}
```

## 前端处理约定

- 事件按 `conversation_id` + `task_id` 路由到对应 store,切换会话后丢弃旧会话事件;
- 收到 `message_start` 时本地创建"本轮助手消息"占位并清空上一轮任务状态;
- `message_delta` 追加到当前流式消息尾部(节流合并 setState,约 80ms);
- `tool_start/tool_finish` 在消息流中渲染可折叠工具卡片;
- `result_ready` 后拉取结果接口填充结果区;
- 断线重连: ①重新申请 ws-token ②`GET /api/tasks/{task_id}` 恢复任务状态 ③若任务仍在运行,`GET /api/tasks/{task_id}/events` 回放事件并重建本轮 UI(先重置再回放,避免重复);
- 历史消息回放走 REST `GET /api/chat/ls/{conversation_id}`,其中 `role=tool` 的消息渲染为工具卡片。
