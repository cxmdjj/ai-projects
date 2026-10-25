import { chatApi } from '../api/chat';
import { getErrorMessage } from '../api/client';
import type { ServerWsEvent } from '../types/ws';

export type WsConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed';

export interface WsSnapshot {
  state: WsConnectionState;
  conversationId: number | null;
  retryCount: number;
  error: string | null;
}

type StateListener = (snapshot: WsSnapshot) => void;
type EventListener = (event: ServerWsEvent) => void;
type ReconnectedListener = () => void;

const BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 15_000];
// 首次连接失败后最多再自动重连 5 次，依次使用上面的 1/2/4/8/15s 间隔。
const MAX_RECONNECT_ATTEMPTS = BACKOFF_MS.length;
const DELTA_THROTTLE_MS = 80;
const HEARTBEAT_MS = 30_000;
const PONG_TIMEOUT_MS = 10_000;
const CONNECT_TIMEOUT_MS = 15_000;

/**
 * 会话级 WebSocket 客户端。
 *
 * 状态机: idle -> connecting -> connected <-> reconnecting -> closed
 * - token 一次性，每次（重）连都重新申请
 * - 断线指数退避 1/2/4/8/15s，最多自动重连 5 次，仍失败则进入 closed
 * - 30s 心跳，10s 未收到 pong 视为连接死亡
 * - message_delta 80ms 合并，其他事件到达前先冲刷，保证事件顺序
 * - 会话切换/断开时丢弃旧连接事件与未冲刷增量
 */
class ConversationWsClient {
  private state: WsConnectionState = 'idle';
  private conversationId: number | null = null;
  private socket: WebSocket | null = null;
  private generation = 0;
  private deliberateClose = false;
  private failureCount = 0;
  private hasConnectedOnce = false;
  private lastError: string | null = null;

  private reconnectTimer: number | null = null;
  private connectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private pongTimer: number | null = null;
  private deltaTimer: number | null = null;
  private pendingDeltas: Array<{ taskId: number; text: string }> = [];

  private stateListeners = new Set<StateListener>();
  private eventListeners = new Set<EventListener>();
  private reconnectedListeners = new Set<ReconnectedListener>();

  getSnapshot = (): WsSnapshot => ({
    state: this.state,
    conversationId: this.conversationId,
    retryCount: this.failureCount,
    error: this.lastError,
  });

  onState(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.getSnapshot());
    return () => this.stateListeners.delete(listener);
  }

  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  onReconnected(listener: ReconnectedListener): () => void {
    this.reconnectedListeners.add(listener);
    return () => this.reconnectedListeners.delete(listener);
  }

  connect(conversationId: number): void {
    if (
      this.conversationId === conversationId &&
      (this.state === 'connecting' || this.state === 'connected' || this.state === 'reconnecting')
    ) {
      return;
    }
    this.shutdownSocket();
    this.clearAllTimers();
    this.clearPendingDeltas();

    this.conversationId = conversationId;
    this.deliberateClose = false;
    this.failureCount = 0;
    this.hasConnectedOnce = false;
    this.lastError = null;
    this.state = 'connecting';
    this.emitState();
    void this.openSocket(false);
  }

  disconnect(): void {
    this.deliberateClose = true;
    this.generation += 1;
    this.conversationId = null;
    this.failureCount = 0;
    this.hasConnectedOnce = false;
    this.lastError = null;
    this.clearAllTimers();
    this.clearPendingDeltas();
    this.shutdownSocket();
    this.state = 'idle';
    this.emitState();
  }

  reconnectNow(): void {
    if (this.conversationId === null) return;
    this.clearAllTimers();
    this.clearPendingDeltas();
    this.shutdownSocket();
    this.deliberateClose = false;
    this.failureCount = 0;
    this.lastError = null;
    this.state = 'connecting';
    this.emitState();
    void this.openSocket(false);
  }

  sendChatMessage(content: string, attachmentIds: number[] = []): boolean {
    return this.send({
      type: 'chat_message',
      content,
      attachment_ids: attachmentIds,
    });
  }

  sendCancel(taskId: number): boolean {
    return this.send({ type: 'cancel_task', task_id: taskId });
  }

  private send(payload: object): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.socket.send(JSON.stringify(payload));
    return true;
  }

  private async openSocket(isRetry: boolean): Promise<void> {
    const conversationId = this.conversationId;
    if (conversationId === null || this.deliberateClose) return;

    this.clearConnectTimer();
    this.generation += 1;
    const generation = this.generation;
    this.state = isRetry ? 'reconnecting' : 'connecting';
    this.emitState();

    this.connectTimer = window.setTimeout(() => {
      if (generation !== this.generation) return;
      this.handleFailure(generation, '建立实时连接超时');
    }, CONNECT_TIMEOUT_MS);

    try {
      const { websocket_token: token } = await chatApi.getWsToken();
      if (
        generation !== this.generation ||
        this.conversationId !== conversationId ||
        this.deliberateClose
      ) {
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url =
        `${protocol}//${window.location.host}/api/chat/ws/chat` +
        `?websocket_token=${encodeURIComponent(token)}` +
        `&conversation_id=${encodeURIComponent(String(conversationId))}`;

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        this.handleFailure(generation, '无法创建实时连接');
        return;
      }
      this.socket = socket;

      socket.onopen = () => {
        if (generation !== this.generation || socket !== this.socket) {
          socket.close();
          return;
        }
        this.clearConnectTimer();
        this.failureCount = 0;
        this.lastError = null;
        const isRecovery = this.hasConnectedOnce;
        this.hasConnectedOnce = true;
        this.state = 'connected';
        this.emitState();
        this.startHeartbeat();
        if (isRecovery) {
          window.setTimeout(() => {
            if (this.state === 'connected') {
              this.reconnectedListeners.forEach((listener) => listener());
            }
          }, 0);
        }
      };

      socket.onmessage = (message) => {
        if (generation !== this.generation || socket !== this.socket) return;
        this.handleRawMessage(message.data);
      };

      socket.onerror = () => {
        // onclose 会随后触发并进入统一的重连流程。
      };

      socket.onclose = (event) => {
        if (generation !== this.generation) return;
        this.clearHeartbeat();
        this.clearConnectTimer();
        this.socket = null;
        if (this.deliberateClose) return;
        const suffix =
          event.code === 4401
            ? '鉴权令牌失效'
            : event.code === 4403
              ? '无权访问该会话'
              : '实时连接已断开';
        this.handleFailure(generation, this.lastError ?? `${suffix}，正在重连`);
      };
    } catch (error) {
      if (generation !== this.generation) return;
      this.handleFailure(
        generation,
        getErrorMessage(error, '获取实时连接令牌失败'),
      );
    }
  }

  private handleFailure(generation: number, message: string): void {
    if (generation !== this.generation) return;
    this.generation += 1;
    this.clearConnectTimer();
    this.clearHeartbeat();
    this.clearPendingDeltas();
    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      try {
        socket.close();
      } catch {
        // 忽略关闭失败。
      }
    }

    if (this.deliberateClose || this.conversationId === null) return;

    this.failureCount += 1;
    this.lastError = message;

    if (this.failureCount > MAX_RECONNECT_ATTEMPTS) {
      this.state = 'closed';
      this.lastError = '实时连接多次重连失败，已停止自动重连';
      this.emitState();
      return;
    }

    this.state = 'reconnecting';
    this.emitState();
    const delay = BACKOFF_MS[Math.min(this.failureCount - 1, BACKOFF_MS.length - 1)];
    this.clearReconnectTimer();
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (this.deliberateClose || this.conversationId === null) return;
      void this.openSocket(true);
    }, delay);
  }

  private handleRawMessage(raw: unknown): void {
    if (typeof raw !== 'string') return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (!parsed || typeof parsed !== 'object') return;
    const event = parsed as ServerWsEvent;
    if (typeof event.type !== 'string') return;

    if (event.type === 'pong') {
      this.clearPongTimer();
      return;
    }

    const conversationId = this.conversationId;
    if (conversationId === null) return;

    if (event.type === 'message_delta') {
      const delta = event as Extract<ServerWsEvent, { type: 'message_delta' }>;
      if (typeof delta.task_id !== 'number' || typeof delta.delta_text !== 'string') return;
      this.pendingDeltas.push({ taskId: delta.task_id, text: delta.delta_text });
      this.scheduleDeltaFlush();
      return;
    }

    // 非增量事件必须先冲刷已缓存增量，保证工具卡片/状态在正确的文本位置之后。
    this.flushDeltas();
    this.dispatchEvent(event);
  }

  private scheduleDeltaFlush(): void {
    if (this.deltaTimer !== null) return;
    this.deltaTimer = window.setTimeout(() => {
      this.deltaTimer = null;
      this.flushDeltas();
    }, DELTA_THROTTLE_MS);
  }

  private flushDeltas(): void {
    this.clearDeltaTimer();
    if (this.pendingDeltas.length === 0) return;
    const chunks = this.pendingDeltas;
    this.pendingDeltas = [];
    for (const chunk of chunks) {
      this.dispatchEvent({
        type: 'message_delta',
        task_id: chunk.taskId,
        delta_text: chunk.text,
      });
    }
  }

  private clearPendingDeltas(): void {
    this.pendingDeltas = [];
    this.clearDeltaTimer();
  }

  private dispatchEvent(event: ServerWsEvent): void {
    const conversationId = this.conversationId;
    if (conversationId === null) return;
    const eventConversationId =
      'conversation_id' in event ? event.conversation_id : undefined;
    if (eventConversationId !== undefined && eventConversationId !== conversationId) {
      return;
    }
    const routed =
      eventConversationId === undefined
        ? ({ ...event, conversation_id: conversationId } as ServerWsEvent)
        : event;
    this.eventListeners.forEach((listener) => {
      try {
        listener(routed);
      } catch {
        // 单个监听器异常不影响实时连接。
      }
    });
  }

  private startHeartbeat(): void {
    this.clearHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
      try {
        this.socket.send(JSON.stringify({ type: 'ping' }));
      } catch {
        this.socket.close();
        return;
      }
      this.clearPongTimer();
      const socket = this.socket;
      this.pongTimer = window.setTimeout(() => {
        if (this.socket !== socket) return;
        this.lastError = '心跳超时，正在重连';
        try {
          socket.close();
        } catch {
          this.handleFailure(this.generation, '心跳超时，正在重连');
        }
      }, PONG_TIMEOUT_MS);
    }, HEARTBEAT_MS);
  }

  private shutdownSocket(): void {
    this.clearConnectTimer();
    this.clearHeartbeat();
    this.clearDeltaTimer();
    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      try {
        socket.close(1000, 'client disconnect');
      } catch {
        // 忽略关闭失败。
      }
    }
  }

  private clearAllTimers(): void {
    this.clearReconnectTimer();
    this.clearConnectTimer();
    this.clearHeartbeat();
    this.clearDeltaTimer();
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearConnectTimer(): void {
    if (this.connectTimer !== null) {
      window.clearTimeout(this.connectTimer);
      this.connectTimer = null;
    }
  }

  private clearHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.clearPongTimer();
  }

  private clearPongTimer(): void {
    if (this.pongTimer !== null) {
      window.clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  }

  private clearDeltaTimer(): void {
    if (this.deltaTimer !== null) {
      window.clearTimeout(this.deltaTimer);
      this.deltaTimer = null;
    }
  }

  private emitState(): void {
    const snapshot = this.getSnapshot();
    this.stateListeners.forEach((listener) => listener(snapshot));
  }
}

export const wsClient = new ConversationWsClient();
