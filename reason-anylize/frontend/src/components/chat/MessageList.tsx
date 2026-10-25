import { useEffect, useRef, useState } from 'react';
import {
  ArrowDownOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  FileTextOutlined,
  PaperClipOutlined,
  SyncOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { Button, Collapse, Empty, Spin, Tag, Tooltip } from 'antd';
import { useChatStore } from '../../stores/chatStore';
import type { UIAttachment, UIMessage } from '../../types/chat';
import { openDownload } from '../../utils/browser';
import { formatDateTime, formatFileSize, getToolLabel } from '../../utils/format';
import MarkdownContent from './MarkdownContent';

function attachmentTypeLabel(name: string): string {
  const ext = name.split('.').pop();
  return ext ? ext.toUpperCase().slice(0, 6) : 'FILE';
}

function MessageAttachments({ attachments }: { attachments: UIAttachment[] }) {
  if (!attachments.length) return null;
  return (
    <div className="message-attachments">
      {attachments.map((attachment, index) => {
        const clickable = typeof attachment.attachment_id === 'number';
        return (
          <Tooltip
            key={`${attachment.file_name}-${attachment.attachment_id ?? index}`}
            title={clickable ? '点击下载附件' : attachment.file_name}
          >
            <button
              type="button"
              className="message-attachment"
              disabled={!clickable}
              onClick={() => {
                if (attachment.attachment_id) {
                  openDownload(`/api/attachment/get?attachment_id=${attachment.attachment_id}`);
                }
              }}
            >
              <span className="message-attachment__icon">
                <FileTextOutlined />
              </span>
              <span className="message-attachment__body">
                <span className="message-attachment__name">{attachment.file_name}</span>
                <span className="message-attachment__meta">
                  {attachmentTypeLabel(attachment.file_name)} · {formatFileSize(attachment.file_size)}
                </span>
              </span>
            </button>
          </Tooltip>
        );
      })}
    </div>
  );
}

function ToolMessage({ message }: { message: UIMessage }) {
  const running = message.toolStatus === 'running';
  const failed = message.toolStatus === 'error' || message.toolStatus === 'failed';
  const statusLabel = running ? '执行中' : failed ? '执行失败' : '执行完成';
  const header = (
    <div className="tool-card__header" onClick={(event) => event.stopPropagation()}>
      <span className={`tool-card__icon${running ? ' is-running' : ''}`}>
        <ToolOutlined />
      </span>
      <span className="tool-card__title">{getToolLabel(message.toolName)}</span>
      <code className="tool-card__name">{message.toolName || 'tool'}</code>
      <Tag
        className="tool-card__status"
        color={running ? 'processing' : failed ? 'error' : 'success'}
        icon={
          running ? (
            <SyncOutlined spin />
          ) : failed ? (
            <CloseCircleFilled />
          ) : (
            <CheckCircleFilled />
          )
        }
        bordered={false}
      >
        {statusLabel}
      </Tag>
    </div>
  );
  const summary = message.toolSummary || message.content;

  return (
    <div className="message-row message-row--tool">
      <div className="message-avatar message-avatar--tool">
        <PaperClipOutlined />
      </div>
      <div className="tool-card">
        {running && !summary ? (
          <div className="tool-card__running">{header}</div>
        ) : (
          <Collapse
            ghost
            size="small"
            className="tool-card__collapse"
            items={[
              {
                key: 'detail',
                label: header,
                children: (
                  <pre className="tool-card__summary">
                    {summary || '工具已执行完成，未返回摘要。'}
                  </pre>
                ),
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: UIMessage }) {
  if (message.role === 'tool') return <ToolMessage message={message} />;

  const isUser = message.role === 'user';
  return (
    <div className={`message-row ${isUser ? 'message-row--user' : 'message-row--assistant'}`}>
      {!isUser && (
        <div className="message-avatar message-avatar--assistant">
          <span>析</span>
        </div>
      )}
      <div className={`message-column ${isUser ? 'message-column--user' : ''}`}>
        <div className="message-meta">
          <span className="message-author">{isUser ? '我' : '分析助手'}</span>
          {message.streaming && <span className="message-live">实时生成</span>}
          {message.createdAt && (
            <span className="message-time">{formatDateTime(message.createdAt)}</span>
          )}
        </div>
        <div
          className={`message-bubble ${isUser ? 'message-bubble--user' : 'message-bubble--assistant'}`}
        >
          {isUser ? (
            <div className="message-plain-text">{message.content}</div>
          ) : message.content ? (
            <MarkdownContent content={message.content} />
          ) : (
            <div className="typing-indicator" aria-label="正在生成分析">
              <span />
              <span />
              <span />
            </div>
          )}
          {message.streaming && message.content && <span className="streaming-caret" />}
        </div>
        {isUser && message.attachments && (
          <MessageAttachments attachments={message.attachments} />
        )}
      </div>
      {isUser && (
        <div className="message-avatar message-avatar--user">
          <span>我</span>
        </div>
      )}
    </div>
  );
}

export default function MessageList() {
  const messages = useChatStore((state) => state.messages);
  const loading = useChatStore((state) => state.loadingHistory);
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);
  const forceScrollRef = useRef(false);
  const [showJump, setShowJump] = useState(false);

  const scrollToBottom = (smooth = false) => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
  };

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.role === 'user') {
      forceScrollRef.current = true;
    }
    if (forceScrollRef.current || autoScrollRef.current) {
      forceScrollRef.current = false;
      const handle = window.requestAnimationFrame(() => scrollToBottom());
      return () => window.cancelAnimationFrame(handle);
    }
    return undefined;
  }, [messages]);

  useEffect(() => {
    if (!loading) {
      const handle = window.requestAnimationFrame(() => scrollToBottom());
      return () => window.cancelAnimationFrame(handle);
    }
    return undefined;
  }, [loading]);

  const handleScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    const atBottom = distance < 120;
    autoScrollRef.current = atBottom;
    setShowJump(!atBottom);
  };

  if (loading) {
    return (
      <div className="message-list message-list--loading">
        <Spin tip="正在回放历史消息…">
          <div className="message-loading-space" />
        </Spin>
      </div>
    );
  }

  return (
    <div className="message-list-wrap">
      <div className="message-list" ref={scrollRef} onScroll={handleScroll}>
        {messages.length === 0 ? (
          <div className="message-list__empty">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div>
                  <div className="message-empty-title">开始一轮经营归因分析</div>
                  <div className="message-empty-description">
                    描述你关注的业务问题，例如“为什么厨房小家电转化率偏低？”
                    <br />
                    也可以先上传 CSV / Excel 等资料，再结合数据提问。
                  </div>
                </div>
              }
            />
          </div>
        ) : (
          <div className="message-list__inner">
            {messages.map((message) => (
              <MessageBubble key={message.key} message={message} />
            ))}
            <div className="message-list__bottom-space" />
          </div>
        )}
      </div>
      {showJump && (
        <Button
          className="scroll-bottom-button"
          shape="circle"
          icon={<ArrowDownOutlined />}
          onClick={() => {
            autoScrollRef.current = true;
            scrollToBottom(true);
          }}
        />
      )}
    </div>
  );
}
