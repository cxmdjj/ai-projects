import { useEffect, useRef, useState } from 'react';
import {
  CheckCircleFilled,
  CloseOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  SendOutlined,
  StopOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { TextAreaRef } from 'antd/es/input/TextArea';
import {
  Alert,
  App as AntdApp,
  Button,
  Input,
  Progress,
  Tooltip,
  Upload,
} from 'antd';
import { attachmentApi } from '../../api/attachment';
import { getErrorMessage } from '../../api/client';
import { useAttachmentStore } from '../../stores/attachmentStore';
import { useChatStore } from '../../stores/chatStore';
import { useTaskStore } from '../../stores/taskStore';
import type { UIAttachment } from '../../types/chat';
import { formatFileSize, isTaskActive } from '../../utils/format';
import { wsClient, type WsSnapshot } from '../../ws/wsClient';

const MAX_FILE_BYTES = 20 * 1024 * 1024;

interface SelectedFile {
  key: string;
  name: string;
  size: number;
  type: string;
  progress: number;
  status: 'uploading' | 'done' | 'error';
  attachmentId?: number;
  error?: string;
}

interface Props {
  conversationId: number | null;
  wsSnapshot: WsSnapshot;
}

let selectedSeq = 0;

export default function ChatInput({ conversationId, wsSnapshot }: Props) {
  const { message } = AntdApp.useApp();
  const [value, setValue] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [canceling, setCanceling] = useState(false);
  const textAreaRef = useRef<TextAreaRef>(null);
  const currentConversationRef = useRef(conversationId);

  const sending = useChatStore((state) => state.sending);
  const loadingHistory = useChatStore((state) => state.loadingHistory);
  const lockError = useChatStore((state) => state.lockError);
  const setLockError = useChatStore((state) => state.setLockError);
  const appendUserMessage = useChatStore((state) => state.appendUserMessage);
  const setSending = useChatStore((state) => state.setSending);
  const task = useTaskStore((state) => state.task);

  const taskRunning = isTaskActive(task?.task_status);
  const uploading = selectedFiles.some((file) => file.status === 'uploading');
  const ready = wsSnapshot.state === 'connected';

  useEffect(() => {
    if (currentConversationRef.current !== conversationId) {
      currentConversationRef.current = conversationId;
      setSelectedFiles([]);
      setValue('');
      setCanceling(false);
    }
  }, [conversationId]);

  useEffect(() => {
    if (!taskRunning) setCanceling(false);
  }, [taskRunning]);

  useEffect(() => {
    // 发送后若在 message_start 前断线，避免发送态永久卡住。
    if (wsSnapshot.state === 'reconnecting' || wsSnapshot.state === 'closed') {
      setSending(false);
    }
  }, [wsSnapshot.state, setSending]);

  const handleUpload = async (file: File) => {
    if (!conversationId) {
      message.warning('请先选择或新建会话');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      message.error('文件超过 20MB 上限');
      return;
    }

    selectedSeq += 1;
    const key = `upload-${Date.now()}-${selectedSeq}`;
    const initial: SelectedFile = {
      key,
      name: file.name,
      size: file.size,
      type: file.type || file.name.split('.').pop() || 'file',
      progress: 0,
      status: 'uploading',
    };
    setSelectedFiles((current) => [...current, initial]);

    const startedConversation = conversationId;
    try {
      const result = await attachmentApi.upload(startedConversation, file, (percent) => {
        setSelectedFiles((current) =>
          current.map((item) => (item.key === key ? { ...item, progress: percent } : item)),
        );
      });
      setSelectedFiles((current) =>
        current.map((item) =>
          item.key === key
            ? {
                ...item,
                progress: 100,
                status: 'done',
                attachmentId: result.attachment_id,
                name: result.file_name,
              }
            : item,
        ),
      );
      if (useAttachmentStore.getState().conversationId === startedConversation) {
        void useAttachmentStore.getState().fetchAttachments(startedConversation);
      }
    } catch (error) {
      const errorMessage = getErrorMessage(error, '附件上传失败');
      setSelectedFiles((current) =>
        current.map((item) =>
          item.key === key ? { ...item, status: 'error', error: errorMessage } : item,
        ),
      );
      message.error(`${file.name}：${errorMessage}`);
    }
  };

  const removeSelected = (key: string) => {
    setSelectedFiles((current) => current.filter((file) => file.key !== key));
  };

  const handleCancel = () => {
    if (!task || !taskRunning) return;
    if (!ready) {
      message.error('实时连接已断开，暂时无法取消任务，请等待重连');
      return;
    }
    const sent = wsClient.sendCancel(task.task_id);
    if (!sent) {
      message.error('取消请求发送失败，请稍后重试');
      return;
    }
    setCanceling(true);
    message.info('已发送取消请求，任务将在当前步骤后停止');
  };

  const handleSend = () => {
    if (!conversationId) {
      message.warning('请先选择或新建会话');
      return;
    }
    if (!ready) {
      message.error('实时连接尚未就绪，请等待重连后再发送');
      return;
    }
    if (taskRunning) {
      message.info('当前分析尚未结束，请等待完成或取消任务');
      return;
    }
    if (loadingHistory) {
      message.info('历史消息仍在加载，请稍候');
      return;
    }
    if (uploading) {
      message.warning('附件仍在上传中，请稍候');
      return;
    }
    if (sending) return;

    const content = value.trim();
    const doneFiles = selectedFiles.filter(
      (file) => file.status === 'done' && typeof file.attachmentId === 'number',
    );
    if (!content && doneFiles.length === 0) {
      message.warning('请输入分析问题或添加附件');
      return;
    }

    const attachmentIds = doneFiles
      .map((file) => file.attachmentId)
      .filter((id): id is number => typeof id === 'number');
    const sent = wsClient.sendChatMessage(content, attachmentIds);
    if (!sent) {
      message.error('消息发送失败，实时连接可能已断开');
      setSending(false);
      return;
    }

    const attachments: UIAttachment[] = doneFiles.map((file) => ({
      attachment_id: file.attachmentId,
      file_name: file.name,
      file_type: file.type,
      file_size: file.size,
    }));
    appendUserMessage(content, attachments);
    setLockError(null);
    setValue('');
    setSelectedFiles([]);
    window.setTimeout(() => textAreaRef.current?.focus(), 0);
  };

  const connectedText = (() => {
    if (!conversationId) return '选择会话后可发送消息';
    if (wsSnapshot.state === 'connecting') return '正在建立实时连接…';
    if (wsSnapshot.state === 'reconnecting') return '实时连接中断，正在重连…';
    if (wsSnapshot.state === 'closed') return '实时连接不可用，请刷新或重新连接';
    if (!ready) return '等待实时连接';
    return 'Enter 发送，Shift + Enter 换行';
  })();

  return (
    <div className="chat-composer-wrap">
      <div className="chat-composer">
        {lockError && (
          <Alert
            type="warning"
            showIcon
            closable
            className="composer-alert"
            message={lockError}
            onClose={() => setLockError(null)}
          />
        )}

        {taskRunning && (
          <div className="composer-running-strip">
            <span className="running-pulse" />
            <span>分析任务正在执行，完成或取消后可继续提问</span>
          </div>
        )}

        {selectedFiles.length > 0 && (
          <div className="composer-attachments">
            {selectedFiles.map((file) => (
              <div
                className={`composer-file${file.status === 'error' ? ' has-error' : ''}`}
                key={file.key}
              >
                <div className="composer-file__icon">
                  <FileTextOutlined />
                </div>
                <div className="composer-file__body">
                  <div className="composer-file__name" title={file.name}>
                    {file.name}
                  </div>
                  <div className="composer-file__meta">
                    {formatFileSize(file.size)}
                    {file.status === 'uploading' && (
                      <span className="file-status">
                        <LoadingOutlined spin /> 上传中
                      </span>
                    )}
                    {file.status === 'done' && (
                      <span className="file-status file-status--success">
                        <CheckCircleFilled /> 已就绪
                      </span>
                    )}
                    {file.status === 'error' && (
                      <span className="file-status file-status--error">
                        <WarningOutlined /> 上传失败
                      </span>
                    )}
                  </div>
                  {file.status === 'uploading' && (
                    <Progress
                      percent={file.progress}
                      size="small"
                      showInfo={false}
                      strokeColor="#2563eb"
                    />
                  )}
                </div>
                <Button
                  type="text"
                  size="small"
                  className="composer-file__remove"
                  icon={<CloseOutlined />}
                  aria-label="移除附件"
                  onClick={() => removeSelected(file.key)}
                />
              </div>
            ))}
          </div>
        )}

        <div className="composer-box">
          <Input.TextArea
            ref={textAreaRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onPressEnter={(event) => {
              if (event.shiftKey || event.nativeEvent.isComposing) return;
              event.preventDefault();
              handleSend();
            }}
            placeholder={
              conversationId
                ? '输入经营问题，例如：为什么最近 30 天复购率下降了？'
                : '请先选择或新建一个会话'
            }
            autoSize={{ minRows: 2, maxRows: 7 }}
            disabled={!conversationId}
            className="composer-textarea"
          />
          <div className="composer-actions">
            <div className="composer-actions__left">
              <Upload
                multiple
                showUploadList={false}
                beforeUpload={(file) => {
                  void handleUpload(file as File);
                  return Upload.LIST_IGNORE;
                }}
                disabled={!conversationId || taskRunning || uploading}
              >
                <Tooltip
                  title={
                    taskRunning
                      ? '分析进行中，暂不能添加附件'
                      : '上传附件（单文件不超过 20MB）'
                  }
                >
                  <Button
                    type="text"
                    icon={<PaperClipOutlined />}
                    disabled={!conversationId || taskRunning}
                    className="composer-clip-button"
                  >
                    附件
                  </Button>
                </Tooltip>
              </Upload>
              <span className="composer-hint">{connectedText}</span>
            </div>
            <div className="composer-actions__right">
              {taskRunning ? (
                <Button
                  danger
                  icon={<StopOutlined />}
                  loading={canceling}
                  onClick={handleCancel}
                >
                  取消分析
                </Button>
              ) : (
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={sending}
                  disabled={
                    !conversationId ||
                    !ready ||
                    loadingHistory ||
                    uploading ||
                    sending ||
                    (!value.trim() && selectedFiles.every((file) => file.status !== 'done'))
                  }
                  className="send-button"
                >
                  发送
                </Button>
              )}
            </div>
          </div>
        </div>
        <div className="composer-footnote">
          分析结论由 AI 基于业务数据生成，请结合业务判断审慎使用。
        </div>
      </div>
    </div>
  );
}
