import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ApiOutlined,
  CloudSyncOutlined,
  ExclamationCircleOutlined,
  LogoutOutlined,
  PaperClipOutlined,
  PlusOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Avatar,
  Badge,
  Button,
  Tag,
  Tooltip,
} from 'antd';
import { chatApi } from '../api/chat';
import { getErrorMessage } from '../api/client';
import { taskApi } from '../api/tasks';
import AttachmentSidebar from '../components/attachment/AttachmentSidebar';
import ChatInput from '../components/chat/ChatInput';
import ConversationList from '../components/chat/ConversationList';
import MessageList from '../components/chat/MessageList';
import ResultPanel from '../components/result/ResultPanel';
import TaskPanel from '../components/task/TaskPanel';
import { applyServerEvent, useConversationSocket } from '../hooks/useConversationSocket';
import { useAttachmentStore } from '../stores/attachmentStore';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { useConversationStore } from '../stores/conversationStore';
import { useResultStore } from '../stores/resultStore';
import { useTaskStore } from '../stores/taskStore';
import type { TaskInfo } from '../types/api';
import { formatStepLabel, isTaskActive, roleLabel } from '../utils/format';
import { getLatestTaskId } from '../utils/taskCache';
import { wsClient, type WsSnapshot } from '../ws/wsClient';

function WsStatusTag({ snapshot }: { snapshot: WsSnapshot }) {
  if (snapshot.conversationId === null) return null;
  if (snapshot.state === 'connected') {
    return (
      <Tag bordered={false} color="success" icon={<ApiOutlined />} className="ws-status-tag">
        实时通道已连接
      </Tag>
    );
  }
  if (snapshot.state === 'connecting' || snapshot.state === 'reconnecting') {
    return (
      <Tag bordered={false} color="processing" icon={<CloudSyncOutlined spin />} className="ws-status-tag">
        连接中
      </Tag>
    );
  }
  if (snapshot.state === 'closed') {
    return (
      <Tag bordered={false} color="error" icon={<ExclamationCircleOutlined />} className="ws-status-tag">
        连接中断
      </Tag>
    );
  }
  return null;
}

async function restoreRememberedTask(conversationId: number, isStale: () => boolean): Promise<void> {
  const taskId = getLatestTaskId(conversationId);
  if (!taskId) return;

  let info: TaskInfo;
  try {
    info = await taskApi.get(taskId);
  } catch {
    return;
  }
  if (isStale() || info.conversation_id !== conversationId) return;

  const liveTaskId = useTaskStore.getState().activeTaskId;
  if (liveTaskId !== null && liveTaskId !== taskId) return;

  useTaskStore.getState().applyTaskInfo(info);

  if (!isTaskActive(info.task_status)) {
    if (info.task_status === 'success') {
      void useResultStore.getState().fetchResult(taskId);
    }
    return;
  }

  try {
    const events = await taskApi.events(taskId);
    if (isStale() || info.conversation_id !== conversationId) return;
    const chatState = useChatStore.getState();
    if (chatState.activeTaskId !== null && chatState.activeTaskId !== taskId) return;
    if (useConversationStore.getState().activeConversationId !== conversationId) return;

    useChatStore.getState().resetRound(taskId);
    useTaskStore.getState().prepareReplay(info);
    useResultStore.getState().reset();
    useChatStore.getState().startRound(taskId);
    for (const event of events) {
      applyServerEvent(event, conversationId, true);
    }
    useTaskStore.getState().setRecovering(false);
  } catch {
    useTaskStore.getState().setRecovering(false);
  }
}

export default function WorkbenchPage() {
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const conversations = useConversationStore((state) => state.conversations);
  const activeConversationId = useConversationStore((state) => state.activeConversationId);
  const fetchConversations = useConversationStore((state) => state.fetchConversations);
  const setActiveConversation = useConversationStore((state) => state.setActiveConversation);
  const createConversation = useConversationStore((state) => state.createConversation);
  const clearConversations = useConversationStore((state) => state.clear);

  const attachments = useAttachmentStore((state) => state.attachments);
  const task = useTaskStore((state) => state.task);
  const [attachmentOpen, setAttachmentOpen] = useState(false);
  const [creatingEmpty, setCreatingEmpty] = useState(false);
  const initializedRef = useRef(false);

  const { snapshot, reconnect } = useConversationSocket(activeConversationId);
  const activeConversation = conversations.find(
    (item) => item.conversation_id === activeConversationId,
  );
  const running = isTaskActive(task?.task_status);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    void (async () => {
      try {
        const items = await fetchConversations();
        if (useConversationStore.getState().activeConversationId === null && items.length > 0) {
          const preferred = items.find((item) => item.status !== 'archived') ?? items[0];
          setActiveConversation(preferred.conversation_id);
        }
      } catch (error) {
        message.error(getErrorMessage(error, '会话列表加载失败'));
      }
    })();
  }, [fetchConversations, message, setActiveConversation]);

  useEffect(() => {
    if (activeConversationId === null) {
      useChatStore.getState().clear();
      useTaskStore.getState().clear();
      useResultStore.getState().reset();
      useAttachmentStore.getState().reset();
      setAttachmentOpen(false);
      return undefined;
    }

    let stale = false;
    const conversationId = activeConversationId;
    useChatStore.getState().beginLoadHistory(conversationId);
    useTaskStore.getState().clear();
    useResultStore.getState().reset();
    useAttachmentStore.getState().reset();
    void useAttachmentStore.getState().fetchAttachments(conversationId);

    void (async () => {
      try {
        const records = await chatApi.listMessages(conversationId);
        if (stale || useConversationStore.getState().activeConversationId !== conversationId) return;
        useChatStore.getState().loadHistory(conversationId, records);
      } catch (error) {
        if (stale || useConversationStore.getState().activeConversationId !== conversationId) return;
        useChatStore.getState().setLoadingHistory(false);
        message.error(getErrorMessage(error, '历史消息加载失败'));
      }

      if (stale || useConversationStore.getState().activeConversationId !== conversationId) return;
      await restoreRememberedTask(conversationId, () => stale);
    })();

    return () => {
      stale = true;
    };
  }, [activeConversationId, message]);

  useEffect(
    () => () => {
      useChatStore.getState().clear();
      useTaskStore.getState().clear();
      useResultStore.getState().reset();
      useAttachmentStore.getState().reset();
      wsClient.disconnect();
    },
    [],
  );

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // logout 已在 finally 中清理本地登录态。
    }
    clearConversations();
    useChatStore.getState().clear();
    useTaskStore.getState().clear();
    useResultStore.getState().reset();
    useAttachmentStore.getState().reset();
    wsClient.disconnect();
    navigate('/login', { replace: true });
  };

  const handleCreateFromEmpty = async () => {
    if (creatingEmpty) return;
    setCreatingEmpty(true);
    try {
      await createConversation('新会话');
    } catch (error) {
      message.error(getErrorMessage(error, '新建会话失败'));
    } finally {
      setCreatingEmpty(false);
    }
  };

  const displayName = user?.display_name || user?.username || '用户';
  const roleName = roleLabel(user?.role ?? '');

  return (
    <div className="workbench-page">
      <header className="workbench-header">
        <div className="workbench-header__brand">
          <button
            type="button"
            className="brand-button"
            onClick={() => navigate('/workbench')}
            aria-label="返回工作台"
          >
            <div className="brand-mark">析</div>
            <div className="brand-copy">
              <span className="brand-copy__name">经营归因分析</span>
              <span className="brand-copy__sub">REASON WORKSPACE</span>
            </div>
          </button>
          <div className="header-divider" />
          <WsStatusTag snapshot={snapshot} />
        </div>

        <div className="workbench-header__actions">
          <Tooltip title="查看当前会话附件">
            <Badge count={attachments.length} size="small" offset={[-4, 4]}>
              <Button
                icon={<PaperClipOutlined />}
                onClick={() => setAttachmentOpen(true)}
                disabled={activeConversationId === null}
                className="header-button"
              >
                附件
              </Button>
            </Badge>
          </Tooltip>

          {user?.role === 'admin' && (
            <Button
              icon={<SettingOutlined />}
              onClick={() => navigate('/admin')}
              className="header-button"
            >
              管理端
            </Button>
          )}

          <div className="header-user">
            <Avatar className="header-avatar" size={32}>
              {displayName.slice(0, 1)}
            </Avatar>
            <div className="header-user__copy">
              <span className="header-user__name">{displayName}</span>
              <span className="header-user__role">{roleName}</span>
            </div>
          </div>

          <Tooltip title="退出登录">
            <Button
              type="text"
              icon={<LogoutOutlined />}
              className="header-logout"
              onClick={() => void handleLogout()}
            >
              退出
            </Button>
          </Tooltip>
        </div>
      </header>

      {(snapshot.state === 'reconnecting' || snapshot.state === 'closed') && (
        <Alert
          className="ws-alert"
          type={snapshot.state === 'closed' ? 'error' : 'warning'}
          showIcon
          banner
          message={
            snapshot.state === 'closed'
              ? '实时连接已断开，自动重连已停止'
              : `实时连接中断，正在第 ${snapshot.retryCount} 次重连…`
          }
          description={snapshot.error ?? undefined}
          action={
            <Button size="small" onClick={reconnect}>
              立即重连
            </Button>
          }
        />
      )}

      <div className="workbench-main">
        <ConversationList />

        <main className="chat-panel">
          {activeConversationId === null ? (
            <div className="chat-empty-state">
              <div className="chat-empty-illustration">
                <span>析</span>
              </div>
              <h2 className="chat-empty-title">从一个经营问题开始</h2>
              <p className="chat-empty-desc">
                创建会话后，你可以上传业务资料、提出分析问题，并实时查看归因过程与结构化结论。
              </p>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                loading={creatingEmpty}
                onClick={() => void handleCreateFromEmpty()}
              >
                新建会话
              </Button>
            </div>
          ) : (
            <>
              <div className="chat-panel__header">
                <div className="chat-title-block">
                  <div className="chat-title-row">
                    <h1>{activeConversation?.title ?? '会话'}</h1>
                    {activeConversation?.status === 'archived' && (
                      <Tag bordered={false}>已归档</Tag>
                    )}
                    {running && (
                      <Tag color="processing" bordered={false}>
                        分析进行中
                      </Tag>
                    )}
                  </div>
                  <div className="chat-subtitle">
                    {task && running
                      ? formatStepLabel(task.current_step)
                      : '围绕业务问题持续追问，分析助手会维护完整上下文'}
                  </div>
                </div>
              </div>
              <MessageList />
              <ChatInput conversationId={activeConversationId} wsSnapshot={snapshot} />
            </>
          )}
        </main>

        <aside className="insight-sidebar">
          <TaskPanel />
          <ResultPanel />
        </aside>
      </div>

      <AttachmentSidebar
        open={attachmentOpen}
        conversationId={activeConversationId}
        onClose={() => setAttachmentOpen(false)}
      />
    </div>
  );
}
