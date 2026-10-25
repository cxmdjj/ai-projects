import { useCallback, useEffect, useState } from 'react';
import { chatApi } from '../api/chat';
import { getErrorMessage } from '../api/client';
import { taskApi } from '../api/tasks';
import { useAttachmentStore } from '../stores/attachmentStore';
import { useChatStore } from '../stores/chatStore';
import { useConversationStore } from '../stores/conversationStore';
import { useResultStore } from '../stores/resultStore';
import { useTaskStore } from '../stores/taskStore';
import type {
  DoneEvent,
  ErrorEvent,
  MessageDeltaEvent,
  MessageStartEvent,
  ResultReadyEvent,
  ServerWsEvent,
  TaskStatusEvent,
  ToolFinishEvent,
  ToolStartEvent,
} from '../types/ws';
import { isTaskActive } from '../utils/format';
import { wsClient, type WsSnapshot } from '../ws/wsClient';

function refreshConversationList(): void {
  void useConversationStore
    .getState()
    .fetchConversations()
    .catch(() => undefined);
}

function finishTaskUi(taskId: number): void {
  useChatStore.getState().finishRound(taskId);
  useTaskStore.getState().setRecovering(false);
}

/**
 * 将一条服务端事件应用到各 store。
 * expectedConversationId 来自当前连接闭包，避免切换会话后旧事件污染新会话。
 */
function applyServerEvent(
  event: ServerWsEvent,
  expectedConversationId: number,
  replay = false,
): void {
  const activeConversationId = useConversationStore.getState().activeConversationId;
  if (activeConversationId !== expectedConversationId) return;

  const eventConversationId =
    'conversation_id' in event ? event.conversation_id : undefined;
  if (eventConversationId !== undefined && eventConversationId !== expectedConversationId) {
    return;
  }

  switch (event.type) {
    case 'message_start': {
      const startEvent = event as MessageStartEvent;
      const taskState = useTaskStore.getState();
      const chatState = useChatStore.getState();
      const isSameTask = taskState.activeTaskId === startEvent.task_id;
      if (!isSameTask) {
        useResultStore.getState().reset();
        useTaskStore.getState().beginTask(startEvent.task_id, expectedConversationId);
        useChatStore.getState().startRound(startEvent.task_id);
      } else if (chatState.activeTaskId !== startEvent.task_id) {
        useChatStore.getState().startRound(startEvent.task_id);
      } else {
        useChatStore.getState().setSending(false);
      }
      useConversationStore.getState().touchConversation(expectedConversationId);
      break;
    }

    case 'message_delta': {
      const deltaEvent = event as MessageDeltaEvent;
      if (useTaskStore.getState().activeTaskId !== deltaEvent.task_id) return;
      useChatStore.getState().appendDelta(deltaEvent.task_id, deltaEvent.delta_text);
      break;
    }

    case 'tool_start': {
      const toolEvent = event as ToolStartEvent;
      if (useTaskStore.getState().activeTaskId !== toolEvent.task_id) return;
      useTaskStore.getState().addTool(toolEvent.task_id, toolEvent.tool_name);
      useChatStore.getState().addTool(toolEvent.task_id, toolEvent.tool_name);
      break;
    }

    case 'tool_finish': {
      const toolEvent = event as ToolFinishEvent;
      if (useTaskStore.getState().activeTaskId !== toolEvent.task_id) return;
      useTaskStore
        .getState()
        .finishTool(
          toolEvent.task_id,
          toolEvent.tool_name,
          toolEvent.tool_result_summary ?? '',
        );
      useChatStore
        .getState()
        .finishTool(
          toolEvent.task_id,
          toolEvent.tool_name,
          toolEvent.tool_result_summary ?? '',
        );
      break;
    }

    case 'task_status': {
      const statusEvent = event as TaskStatusEvent;
      if (useTaskStore.getState().activeTaskId !== statusEvent.task_id) return;
      useTaskStore
        .getState()
        .updateStatus(statusEvent.task_id, statusEvent.task_status, statusEvent.current_step);
      if (
        statusEvent.task_status === 'success' ||
        statusEvent.task_status === 'failed' ||
        statusEvent.task_status === 'cancelled'
      ) {
        finishTaskUi(statusEvent.task_id);
        refreshConversationList();
      }
      break;
    }

    case 'result_ready': {
      const resultEvent = event as ResultReadyEvent;
      if (useTaskStore.getState().activeTaskId !== resultEvent.task_id) return;
      useTaskStore.getState().setResultReady(resultEvent.task_id, resultEvent.result_id);
      void useResultStore.getState().fetchResult(resultEvent.task_id);
      break;
    }

    case 'error': {
      const errorEvent = event as ErrorEvent;
      if (errorEvent.task_id === null) {
        useChatStore.getState().setLockError(errorEvent.error_message || '消息发送失败');
        return;
      }
      if (useTaskStore.getState().activeTaskId !== errorEvent.task_id) return;
      useTaskStore.getState().applyError(errorEvent.task_id, errorEvent.error_message);
      finishTaskUi(errorEvent.task_id);
      break;
    }

    case 'done': {
      const doneEvent = event as DoneEvent;
      if (useTaskStore.getState().activeTaskId !== doneEvent.task_id) return;
      useTaskStore.getState().markDone(doneEvent.task_id, doneEvent.finished_at);
      finishTaskUi(doneEvent.task_id);
      const task = useTaskStore.getState().task;
      if (task?.task_status === 'success' && !useTaskStore.getState().resultReady) {
        void useResultStore.getState().fetchResult(doneEvent.task_id);
      }
      refreshConversationList();
      break;
    }

    case 'attachment_parsed': {
      if (useAttachmentStore.getState().conversationId === expectedConversationId) {
        void useAttachmentStore.getState().fetchAttachments(expectedConversationId);
      }
      break;
    }

    case 'pong':
      break;

    default:
      if (!replay) {
        // 未知扩展事件静默忽略，保持向前兼容。
      }
      break;
  }
}

async function recoverActiveTask(conversationId: number): Promise<void> {
  const taskState = useTaskStore.getState();
  const current = taskState.task;
  if (!current || current.conversation_id !== conversationId) return;
  if (!isTaskActive(current.task_status) && !taskState.recovering) return;
  if (useConversationStore.getState().activeConversationId !== conversationId) return;

  useTaskStore.getState().setRecovering(true);
  try {
    const info = await taskApi.get(current.task_id);
    if (useConversationStore.getState().activeConversationId !== conversationId) return;

    if (isTaskActive(info.task_status)) {
      // 先取回完整事件，再重置本轮 UI，避免重置后请求失败导致内容丢失。
      const events = await taskApi.events(current.task_id);
      if (useConversationStore.getState().activeConversationId !== conversationId) return;
      useChatStore.getState().resetRound(current.task_id);
      useTaskStore.getState().prepareReplay(info);
      useResultStore.getState().reset();
      const chatState = useChatStore.getState();
      if (chatState.activeTaskId !== current.task_id) {
        useChatStore.getState().startRound(current.task_id);
      }
      for (const event of events) {
        applyServerEvent(event, conversationId, true);
      }
      useTaskStore.getState().setRecovering(false);
      return;
    }

    useTaskStore.getState().applyTaskInfo(info);
    useTaskStore.getState().setRecovering(false);
    useChatStore.getState().finishRound(current.task_id);
    if (info.task_status === 'success') {
      void useResultStore.getState().fetchResult(current.task_id);
    }

    // 终端任务期间可能已产生断线期文本，用历史消息校准一次完整内容。
    try {
      const records = await chatApi.listMessages(conversationId);
      if (useConversationStore.getState().activeConversationId !== conversationId) return;
      const latestChat = useChatStore.getState();
      if (latestChat.activeTaskId !== null && latestChat.activeTaskId !== current.task_id) {
        return;
      }
      useChatStore.getState().replaceMessages(records, conversationId);
      useChatStore.getState().finishRound(current.task_id);
    } catch {
      // 历史校准失败不影响当前 UI。
    }
  } catch (error) {
    useTaskStore.getState().setRecovering(false);
    if (useConversationStore.getState().activeConversationId === conversationId) {
      useChatStore.getState().setLockError(
        `任务状态恢复失败：${getErrorMessage(error, '请稍后重试')}`,
      );
    }
  }
}

export function useConversationSocket(conversationId: number | null): {
  snapshot: WsSnapshot;
  reconnect: () => void;
} {
  const [snapshot, setSnapshot] = useState<WsSnapshot>(wsClient.getSnapshot);

  useEffect(() => {
    if (conversationId === null) {
      wsClient.disconnect();
      setSnapshot(wsClient.getSnapshot());
      return undefined;
    }

    const offState = wsClient.onState((next) => setSnapshot(next));
    const offEvent = wsClient.onEvent((event) => {
      applyServerEvent(event, conversationId);
    });
    const offReconnected = wsClient.onReconnected(() => {
      void recoverActiveTask(conversationId);
    });

    wsClient.connect(conversationId);

    return () => {
      offState();
      offEvent();
      offReconnected();
      wsClient.disconnect();
    };
  }, [conversationId]);

  const reconnect = useCallback(() => {
    wsClient.reconnectNow();
  }, []);

  return { snapshot, reconnect };
}

export { applyServerEvent };
