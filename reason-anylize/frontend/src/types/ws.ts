import type { TaskStatus } from './api';

interface BaseWsEvent {
  /** 客户端根据当前连接补全，便于按会话路由。 */
  conversation_id?: number;
}

export interface MessageStartEvent extends BaseWsEvent {
  type: 'message_start';
  task_id: number;
  conversation_id: number;
}

export interface MessageDeltaEvent extends BaseWsEvent {
  type: 'message_delta';
  task_id: number;
  delta_text: string;
}

export interface ToolStartEvent extends BaseWsEvent {
  type: 'tool_start';
  task_id: number;
  tool_name: string;
}

export interface ToolFinishEvent extends BaseWsEvent {
  type: 'tool_finish';
  task_id: number;
  tool_name: string;
  tool_result_summary: string;
}

export interface TaskStatusEvent extends BaseWsEvent {
  type: 'task_status';
  task_id: number;
  task_status: TaskStatus;
  current_step: string;
}

export interface ResultReadyEvent extends BaseWsEvent {
  type: 'result_ready';
  task_id: number;
  result_id: number;
}

export interface ErrorEvent extends BaseWsEvent {
  type: 'error';
  task_id: number | null;
  error_message: string;
}

export interface DoneEvent extends BaseWsEvent {
  type: 'done';
  task_id: number;
  finished_at: string;
}

export interface AttachmentParsedEvent extends BaseWsEvent {
  type: 'attachment_parsed';
  attachment_id: number;
  parse_status: 'parsed' | 'failed' | string;
}

export interface PongEvent {
  type: 'pong';
}

export interface UnknownWsEvent extends BaseWsEvent {
  type: string;
}

export type ServerWsEvent =
  | MessageStartEvent
  | MessageDeltaEvent
  | ToolStartEvent
  | ToolFinishEvent
  | TaskStatusEvent
  | ResultReadyEvent
  | ErrorEvent
  | DoneEvent
  | AttachmentParsedEvent
  | PongEvent
  | UnknownWsEvent;

export interface ClientChatMessage {
  type: 'chat_message';
  content: string;
  attachment_ids?: number[];
}

export interface ClientCancelTask {
  type: 'cancel_task';
  task_id: number;
}

export interface ClientPing {
  type: 'ping';
}

export type ClientWsMessage = ClientChatMessage | ClientCancelTask | ClientPing;
