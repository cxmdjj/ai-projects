"""WebSocket 连接管理 + 任务事件缓冲(断线回放)。"""

import asyncio
import json
from collections import defaultdict, deque
from typing import Any

from fastapi import WebSocket

EVENT_BUFFER_SIZE = 200


class WSManager:
    
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = defaultdict(set)
        self._events: dict[int, deque[dict]] = defaultdict(lambda: deque(maxlen=EVENT_BUFFER_SIZE))
        self._lock = asyncio.Lock()

    async def connect(self, conversation_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._conns[conversation_id].add(ws)

    async def disconnect(self, conversation_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._conns[conversation_id].discard(ws)
            if not self._conns[conversation_id]:
                self._conns.pop(conversation_id, None)

    async def broadcast(self, conversation_id: int, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._conns.get(conversation_id, ()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                # default=str 兜底 datetime 等非 JSON 类型(done 事件的 finished_at)
                await ws.send_text(json.dumps(event, ensure_ascii=False, default=str))
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns[conversation_id].discard(ws)

    def push_event(self, task_id: int, event: dict[str, Any]) -> None:
        self._events[task_id].append(event)

    def get_events(self, task_id: int) -> list[dict[str, Any]]:
        return list(self._events.get(task_id, ()))

    def drop_events(self, task_id: int) -> None:
        self._events.pop(task_id, None)


ws_manager = WSManager()
