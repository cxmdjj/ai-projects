import { useEffect, useState } from 'react';
import {
  DeleteOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  InboxOutlined,
  SyncOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Button,
  Drawer,
  Empty,
  Popconfirm,
  Progress,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import { attachmentApi } from '../../api/attachment';
import { getErrorMessage } from '../../api/client';
import { useAttachmentStore } from '../../stores/attachmentStore';
import type { AttachmentMeta } from '../../types/api';
import { openDownload } from '../../utils/browser';
import { formatDateTime, formatFileSize } from '../../utils/format';

const { Text } = Typography;
const MAX_FILE_BYTES = 20 * 1024 * 1024;

interface UploadTask {
  key: string;
  name: string;
  percent: number;
  status: 'uploading' | 'done' | 'error';
}

interface Props {
  open: boolean;
  conversationId: number | null;
  onClose: () => void;
}

let uploadSeq = 0;

function fileIcon(fileName: string) {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? '';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return <FileImageOutlined />;
  if (['xls', 'xlsx', 'csv'].includes(ext)) return <FileExcelOutlined />;
  if (ext === 'pdf') return <FilePdfOutlined />;
  return <FileTextOutlined />;
}

function ParseStatusTag({ status }: { status: string }) {
  switch (status) {
    case 'pending':
      return (
        <Tag color="blue" bordered={false}>
          待解析
        </Tag>
      );
    case 'parsing':
      return (
        <Tag color="processing" bordered={false} icon={<SyncOutlined spin />}>
          解析中
        </Tag>
      );
    case 'parsed':
      return (
        <Tag color="success" bordered={false}>
          已解析
        </Tag>
      );
    case 'failed':
      return (
        <Tag color="error" bordered={false}>
          解析失败
        </Tag>
      );
    default:
      return <Tag bordered={false}>{status || '未知'}</Tag>;
  }
}

export default function AttachmentSidebar({ open, conversationId, onClose }: Props) {
  const { message } = AntdApp.useApp();
  const attachments = useAttachmentStore((state) => state.attachments);
  const loading = useAttachmentStore((state) => state.loading);
  const error = useAttachmentStore((state) => state.error);
  const fetchAttachments = useAttachmentStore((state) => state.fetchAttachments);
  const deleteAttachment = useAttachmentStore((state) => state.deleteAttachment);
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const hasPending = attachments.some(
    (item) => item.parse_status === 'pending' || item.parse_status === 'parsing',
  );

  useEffect(() => {
    if (open && conversationId) {
      void fetchAttachments(conversationId);
    }
  }, [open, conversationId, fetchAttachments]);

  // WS 事件驱动优先；保留轮询作为解析状态的兜底。
  useEffect(() => {
    if (!open || !conversationId || !hasPending) return undefined;
    const timer = window.setInterval(() => {
      void fetchAttachments(conversationId);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [open, conversationId, hasPending, fetchAttachments]);

  const handleUpload = async (file: File) => {
    if (!conversationId) {
      message.warning('请先选择会话');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      message.error('文件超过 20MB 上限');
      return;
    }
    uploadSeq += 1;
    const key = `side-upload-${Date.now()}-${uploadSeq}`;
    setUploads((current) => [
      ...current,
      { key, name: file.name, percent: 0, status: 'uploading' },
    ]);

    try {
      await attachmentApi.upload(conversationId, file, (percent) => {
        setUploads((current) =>
          current.map((item) => (item.key === key ? { ...item, percent } : item)),
        );
      });
      setUploads((current) =>
        current.map((item) =>
          item.key === key ? { ...item, percent: 100, status: 'done' } : item,
        ),
      );
      message.success(`${file.name} 上传成功，正在解析`);
      await fetchAttachments(conversationId);
      window.setTimeout(() => {
        setUploads((current) => current.filter((item) => item.key !== key));
      }, 1_800);
    } catch (err) {
      const errorMessage = getErrorMessage(err, '上传失败');
      setUploads((current) =>
        current.map((item) =>
          item.key === key ? { ...item, status: 'error' } : item,
        ),
      );
      message.error(`${file.name}：${errorMessage}`);
    }
  };

  const handleDelete = async (attachment: AttachmentMeta) => {
    setDeletingId(attachment.attachment_id);
    try {
      await deleteAttachment(attachment.attachment_id);
      message.success('附件已删除');
    } catch (err) {
      message.error(getErrorMessage(err, '附件删除失败'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Drawer
      title={
        <div className="attachment-drawer__title">
          <span>附件资料</span>
          <span className="attachment-drawer__count">{attachments.length}</span>
        </div>
      }
      width={440}
      open={open}
      onClose={onClose}
      className="attachment-drawer"
      extra={
        <Upload
          multiple
          showUploadList={false}
          disabled={!conversationId}
          beforeUpload={(file) => {
            void handleUpload(file as File);
            return Upload.LIST_IGNORE;
          }}
        >
          <Button type="primary" size="small" icon={<UploadOutlined />} disabled={!conversationId}>
            上传附件
          </Button>
        </Upload>
      }
    >
      <div className="attachment-intro">
        <InboxOutlined />
        <span>支持上传 CSV、Excel、PDF、图片等资料，单个文件不超过 20MB。</span>
      </div>

      {uploads.length > 0 && (
        <div className="attachment-uploads">
          {uploads.map((task) => (
            <div className={`attachment-upload-item is-${task.status}`} key={task.key}>
              <div className="attachment-upload-item__head">
                <span className="attachment-upload-item__name">{task.name}</span>
                <span className="attachment-upload-item__status">
                  {task.status === 'uploading'
                    ? '上传中'
                    : task.status === 'done'
                      ? '已完成'
                      : '上传失败'}
                </span>
              </div>
              <Progress
                percent={task.percent}
                size="small"
                showInfo={false}
                status={
                  task.status === 'error'
                    ? 'exception'
                    : task.status === 'done'
                      ? 'success'
                      : 'active'
                }
              />
            </div>
          ))}
        </div>
      )}

      {error && <Alert type="warning" showIcon message={error} className="attachment-error" />}

      {!conversationId ? (
        <Empty description="请先选择会话" />
      ) : loading && attachments.length === 0 ? (
        <div className="attachment-loading">
          <Spin />
        </div>
      ) : attachments.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前会话暂无附件">
          <Text type="secondary">上传资料后，分析助手可以检索和引用附件内容。</Text>
        </Empty>
      ) : (
        <div className="attachment-list">
          {attachments.map((attachment) => (
            <div className="attachment-card" key={attachment.attachment_id}>
              <div className="attachment-card__icon">{fileIcon(attachment.file_name)}</div>
              <div className="attachment-card__body">
                <Tooltip title={attachment.file_name}>
                  <div className="attachment-card__name">{attachment.file_name}</div>
                </Tooltip>
                <div className="attachment-card__meta">
                  <Tag bordered={false} className="attachment-type-tag">
                    {(attachment.file_type || 'FILE').toUpperCase()}
                  </Tag>
                  <span>{formatFileSize(attachment.file_size)}</span>
                  <span className="meta-divider">·</span>
                  <span>{formatDateTime(attachment.created_at)}</span>
                </div>
                <div className="attachment-card__status">
                  <ParseStatusTag status={attachment.parse_status} />
                </div>
              </div>
              <Space direction="vertical" size={2} className="attachment-card__actions">
                <Tooltip title="下载">
                  <Button
                    type="text"
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() =>
                      openDownload(attachmentApi.downloadUrl(attachment.attachment_id))
                    }
                  />
                </Tooltip>
                <Popconfirm
                  title="删除附件"
                  description="删除后不可恢复。"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => handleDelete(attachment)}
                >
                  <Tooltip title="删除">
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={deletingId === attachment.attachment_id}
                    />
                  </Tooltip>
                </Popconfirm>
              </Space>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
}
