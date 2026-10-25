import type { ReactNode } from 'react';
import {
  CopyOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  DownOutlined,
  ExportOutlined,
  FileSearchOutlined,
  FundOutlined,
  LinkOutlined,
  NumberOutlined,
  QuestionCircleOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Dropdown,
  Empty,
  Skeleton,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { resultApi, type ExportFormat } from '../../api/results';
import { useResultStore } from '../../stores/resultStore';
import { useTaskStore } from '../../stores/taskStore';
import type { EvidenceItem, KeyMetric } from '../../types/api';
import { copyText, openDownload } from '../../utils/browser';
import {
  confidenceMeta,
  formatDateTime,
  getTaskStatusMeta,
  isTaskActive,
} from '../../utils/format';

const { Text, Paragraph } = Typography;

const metricColumns: ColumnsType<KeyMetric> = [
  {
    title: '关键指标',
    dataIndex: 'metric_name',
    key: 'metric_name',
    className: 'metric-name-cell',
    ellipsis: true,
  },
  {
    title: '数值',
    key: 'metric_value',
    width: 110,
    render: (_, record) => (
      <span className="metric-value">
        {String(record.metric_value)}
        {record.metric_unit && <span className="metric-unit">{record.metric_unit}</span>}
      </span>
    ),
  },
  {
    title: '统计周期',
    dataIndex: 'metric_period',
    key: 'metric_period',
    width: 105,
    render: (value: string) => <span className="metric-period">{value || '—'}</span>,
  },
];

const sourceTypeMeta: Record<string, { color: string; label: string }> = {
  database: { color: 'blue', label: '数据库' },
  file: { color: 'geekblue', label: '文件' },
  attachment: { color: 'orange', label: '附件' },
  text: { color: 'cyan', label: '文本' },
};

function Section({
  index,
  title,
  icon,
  children,
  tone,
}: {
  index: string;
  title: string;
  icon: ReactNode;
  children: ReactNode;
  tone?: string;
}) {
  return (
    <section className={`result-section${tone ? ` result-section--${tone}` : ''}`}>
      <div className="result-section__header">
        <span className="result-section__index">{index}</span>
        <span className="result-section__icon">{icon}</span>
        <h3 className="result-section__title">{title}</h3>
      </div>
      <div className="result-section__body">{children}</div>
    </section>
  );
}

function EvidenceCard({ item, index }: { item: EvidenceItem; index: number }) {
  const sourceMeta = sourceTypeMeta[item.source_type] ?? {
    color: 'default',
    label: item.source_type || '其他',
  };
  const confidence = confidenceMeta(item.confidence);
  return (
    <div className="evidence-card">
      <div className="evidence-card__top">
        <span className="evidence-card__index">证据 {index + 1}</span>
        <div className="evidence-card__tags">
          <Tag bordered={false} color={sourceMeta.color}>
            {sourceMeta.label}
          </Tag>
          <Tag bordered={false} color={confidence.color}>
            {confidence.label}
          </Tag>
        </div>
      </div>
      <div className="evidence-source">
        <DatabaseOutlined />
        <span>{item.source_name || '未命名来源'}</span>
      </div>
      <div className="evidence-text">{item.evidence_text}</div>
      {item.related_metric && (
        <div className="evidence-metric">
          <LinkOutlined />
          <span>关联指标：{item.related_metric}</span>
        </div>
      )}
    </div>
  );
}

export default function ResultPanel() {
  const { message } = AntdApp.useApp();
  const result = useResultStore((state) => state.result);
  const loading = useResultStore((state) => state.loading);
  const error = useResultStore((state) => state.error);
  const task = useTaskStore((state) => state.task);
  const resultReady = useTaskStore((state) => state.resultReady);

  const handleCopy = async () => {
    if (!result) return;
    const ok = await copyText(result.result_markdown || '');
    if (ok) message.success('Markdown 已复制到剪贴板');
    else message.error('复制失败，请手动选择文本复制');
  };

  const handleExport = (format: ExportFormat) => {
    if (!result) return;
    openDownload(resultApi.exportUrl(result.task_id, format));
  };

  const exportMenu = {
    items: [
      { key: 'md', label: '导出 Markdown (.md)' },
      { key: 'html', label: '导出 HTML (.html)' },
      { key: 'json', label: '导出 JSON (.json)' },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'md' || key === 'html' || key === 'json') {
        handleExport(key);
      }
    },
  };

  const headerExtra = result ? (
    <div className="result-actions">
      <Tooltip title="复制完整 Markdown">
        <Button size="small" icon={<CopyOutlined />} onClick={() => void handleCopy()}>
          复制
        </Button>
      </Tooltip>
      <Dropdown menu={exportMenu} trigger={['click']}>
        <Button size="small" icon={<ExportOutlined />}>
          导出 <DownOutlined />
        </Button>
      </Dropdown>
      <Tooltip title={result.result_file_path ? '下载系统生成的分析报告' : '报告文件尚未生成'}>
        <Button
          size="small"
          type="primary"
          ghost
          icon={<DownloadOutlined />}
          disabled={!result.result_file_path}
          onClick={() => openDownload(resultApi.downloadUrl(result.task_id))}
        >
          下载报告
        </Button>
      </Tooltip>
    </div>
  ) : null;

  return (
    <Card
      className="result-panel"
      variant="borderless"
      title={
        <div className="result-panel__heading">
          <span className="section-eyebrow">ANALYSIS RESULT</span>
          <span className="result-panel__title">归因结果</span>
        </div>
      }
      extra={headerExtra}
    >
      {loading ? (
        <div className="result-loading">
          <Skeleton active paragraph={{ rows: 6 }} />
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
      ) : result ? (
        <div className="result-content">
          <div className="result-meta">
            <span>结果 #{result.result_id}</span>
            <span>任务 #{result.task_id}</span>
            <span>{formatDateTime(result.created_at)}</span>
          </div>

          <Section index="01" title="问题定义" icon={<QuestionCircleOutlined />}>
            <Paragraph className="result-paragraph">{result.problem_definition || '—'}</Paragraph>
          </Section>

          <Section index="02" title="关键指标" icon={<FundOutlined />}>
            {result.key_metrics.length ? (
              <Table<KeyMetric>
                className="metric-table"
                columns={metricColumns}
                dataSource={result.key_metrics.map((item, index) => ({ ...item, key: index }))}
                rowKey={(record) => `${record.metric_name}-${record.metric_period}-${record.metric_value}`}
                pagination={false}
                size="small"
                tableLayout="fixed"
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无关键指标" />
            )}
          </Section>

          <Section index="03" title="证据列表" icon={<FileSearchOutlined />}>
            {result.evidence_list.length ? (
              <div className="evidence-list">
                {result.evidence_list.map((item, index) => (
                  <EvidenceCard
                    key={`${item.source_name}-${index}`}
                    item={item}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无证据" />
            )}
          </Section>

          <Section index="04" title="归因结论" icon={<NumberOutlined />} tone="conclusion">
            <div className="result-long-text">{result.conclusion_text || '—'}</div>
          </Section>

          <Section index="05" title="待补充数据" icon={<SafetyCertificateOutlined />} tone="muted">
            <div className="result-long-text">{result.missing_data_text || '暂无待补充数据'}</div>
          </Section>

          <Section index="06" title="下一步建议" icon={<RocketOutlined />}>
            {result.next_action_text.length ? (
              <ol className="next-actions">
                {result.next_action_text.map((action, index) => (
                  <li key={`${action}-${index}`}>
                    <span className="next-actions__index">{String(index + 1).padStart(2, '0')}</span>
                    <span>{action}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无建议" />
            )}
          </Section>

          <div className="result-footer">
            <Text type="secondary">
              结果由模型结合工具证据生成，可在右上角复制或导出完整报告。
            </Text>
          </div>
        </div>
      ) : error ? (
        <Alert
          type="warning"
          showIcon
          className="result-empty-alert"
          message="结果暂不可用"
          description={error}
        />
      ) : resultReady || isTaskActive(task?.task_status) ? (
        <div className="result-pending">
          <div className="result-pending__pulse" />
          <div className="result-pending__title">正在生成分析结果…</div>
          <div className="result-pending__desc">结构化六部分结果生成后将自动展示</div>
        </div>
      ) : (
        <div className="result-idle">
          <div className="result-idle__icon">
            <FundOutlined />
          </div>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <div className="result-idle__copy">
                <div className="result-idle__title">暂无分析结果</div>
                <div className="result-idle__desc">
                  完成任务后将在此展示问题定义、关键指标、证据链、归因结论、待补充数据与下一步建议。
                </div>
              </div>
            }
          />
          {task?.task_status && (
            <div className="result-idle__task">
              当前任务状态：
              <Tag color={getTaskStatusMeta(task.task_status).color} bordered={false}>
                {getTaskStatusMeta(task.task_status).label}
              </Tag>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
