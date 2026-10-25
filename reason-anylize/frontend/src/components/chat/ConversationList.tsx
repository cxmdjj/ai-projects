import { useState } from 'react';
import {
  DeleteOutlined,
  EditOutlined,
  InboxOutlined,
  PlusOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import {
  App as AntdApp,
  Button,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Skeleton,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import { getErrorMessage } from '../../api/client';
import { useConversationStore } from '../../stores/conversationStore';
import type { Conversation } from '../../types/api';
import { formatRelativeTime } from '../../utils/format';

const { Text } = Typography;

interface Props {
  onConversationSelected?: (conversation: Conversation) => void;
}

export default function ConversationList({ onConversationSelected }: Props) {
  const { message } = AntdApp.useApp();
  const conversations = useConversationStore((state) => state.conversations);
  const activeId = useConversationStore((state) => state.activeConversationId);
  const loading = useConversationStore((state) => state.loading);
  const initialized = useConversationStore((state) => state.initialized);
  const error = useConversationStore((state) => state.error);
  const createConversation = useConversationStore((state) => state.createConversation);
  const renameConversation = useConversationStore((state) => state.renameConversation);
  const setArchived = useConversationStore((state) => state.setArchived);
  const deleteConversation = useConversationStore((state) => state.deleteConversation);
  const setActiveConversation = useConversationStore((state) => state.setActiveConversation);

  const [creating, setCreating] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [archivingId, setArchivingId] = useState<number | null>(null);

  const activeConversations = conversations.filter((item) => item.status !== 'archived');
  const archivedConversations = conversations.filter((item) => item.status === 'archived');

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const conversation = await createConversation('新会话');
      onConversationSelected?.(conversation);
      message.success('已创建新会话');
    } catch (err) {
      message.error(getErrorMessage(err, '新建会话失败'));
    } finally {
      setCreating(false);
    }
  };

  const handleSelect = (conversation: Conversation) => {
    if (conversation.conversation_id === activeId) return;
    setActiveConversation(conversation.conversation_id);
    onConversationSelected?.(conversation);
  };

  const openRename = (conversation: Conversation) => {
    setRenameTarget(conversation);
    setRenameValue(conversation.title);
  };

  const submitRename = async () => {
    if (!renameTarget) return;
    const title = renameValue.trim();
    if (!title) {
      message.warning('请输入会话标题');
      return;
    }
    setRenaming(true);
    try {
      await renameConversation(renameTarget.conversation_id, title);
      message.success('会话已重命名');
      setRenameTarget(null);
    } catch (err) {
      message.error(getErrorMessage(err, '重命名失败'));
    } finally {
      setRenaming(false);
    }
  };

  const handleArchive = async (conversation: Conversation) => {
    const archived = conversation.status !== 'archived';
    setArchivingId(conversation.conversation_id);
    try {
      await setArchived(conversation.conversation_id, archived);
      message.success(archived ? '会话已归档' : '已取消归档');
    } catch (err) {
      message.error(getErrorMessage(err, archived ? '归档失败' : '取消归档失败'));
    } finally {
      setArchivingId(null);
    }
  };

  const handleDelete = async (conversation: Conversation) => {
    try {
      await deleteConversation(conversation.conversation_id);
      message.success('会话已删除');
    } catch (err) {
      message.error(getErrorMessage(err, '删除会话失败'));
    }
  };

  const renderItem = (conversation: Conversation) => {
    const selected = conversation.conversation_id === activeId;
    const archived = conversation.status === 'archived';
    return (
      <div
        key={conversation.conversation_id}
        className={`conversation-item${selected ? ' is-active' : ''}${archived ? ' is-archived' : ''}`}
        role="button"
        tabIndex={0}
        onClick={() => handleSelect(conversation)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handleSelect(conversation);
          }
        }}
      >
        <div className="conversation-item__main">
          <div className="conversation-item__title-row">
            <span className="conversation-item__title" title={conversation.title}>
              {conversation.title || '未命名会话'}
            </span>
            {archived && (
              <Tag bordered={false} className="conversation-archive-tag">
                已归档
              </Tag>
            )}
          </div>
          <span className="conversation-item__time">
            {conversation.last_message_at
              ? formatRelativeTime(conversation.last_message_at)
              : '暂无消息'}
          </span>
        </div>

        <div
          className="conversation-item__actions"
          onClick={(event) => event.stopPropagation()}
        >
          <Tooltip title="重命名">
            <Button
              type="text"
              size="small"
              className="conversation-action"
              icon={<EditOutlined />}
              onClick={() => openRename(conversation)}
            />
          </Tooltip>
          <Tooltip title={archived ? '取消归档' : '归档'}>
            <Button
              type="text"
              size="small"
              className="conversation-action"
              icon={archived ? <UndoOutlined /> : <InboxOutlined />}
              loading={archivingId === conversation.conversation_id}
              onClick={() => void handleArchive(conversation)}
            />
          </Tooltip>
          <Popconfirm
            title="删除会话"
            description="消息、附件、任务与结果都将被删除，且不可恢复。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(conversation)}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                danger
                className="conversation-action"
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </div>
      </div>
    );
  };

  return (
    <aside className="conversation-sidebar">
      <div className="conversation-sidebar__heading">
        <div>
          <Text className="section-eyebrow">CONVERSATIONS</Text>
          <div className="conversation-sidebar__title">会话</div>
        </div>
        <span className="conversation-count">{conversations.length}</span>
      </div>

      <Button
        type="primary"
        icon={<PlusOutlined />}
        block
        className="new-conversation-button"
        loading={creating}
        onClick={() => void handleCreate()}
      >
        新建会话
      </Button>

      <div className="conversation-sidebar__list">
        {!initialized && loading ? (
          <div className="conversation-skeleton">
            <Skeleton active paragraph={{ rows: 3 }} title={false} />
            <Skeleton active paragraph={{ rows: 3 }} title={false} />
          </div>
        ) : conversations.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={error ? '会话加载失败' : '暂无会话'}
            className="conversation-empty"
          >
            <Button type="link" size="small" onClick={() => void handleCreate()}>
              创建第一个会话
            </Button>
          </Empty>
        ) : (
          <>
            <div className="conversation-group-label">进行中</div>
            {activeConversations.length === 0 ? (
              <div className="conversation-group-empty">暂无进行中的会话</div>
            ) : (
              activeConversations.map(renderItem)
            )}
            {archivedConversations.length > 0 && (
              <>
                <div className="conversation-group-label conversation-group-label--archived">
                  已归档
                </div>
                {archivedConversations.map(renderItem)}
              </>
            )}
          </>
        )}
      </div>

      <div className="conversation-sidebar__footer">
        <span className="status-dot" />
        会话数据由当前账号隔离
      </div>

      <Modal
        title="重命名会话"
        open={renameTarget !== null}
        onCancel={() => {
          if (!renaming) setRenameTarget(null);
        }}
        onOk={() => void submitRename()}
        okText="保存"
        cancelText="取消"
        confirmLoading={renaming}
        destroyOnHidden
      >
        <Input
          value={renameValue}
          onChange={(event) => setRenameValue(event.target.value)}
          onPressEnter={() => void submitRename()}
          placeholder="输入会话标题"
          maxLength={256}
          showCount
          autoFocus
        />
      </Modal>
    </aside>
  );
}
