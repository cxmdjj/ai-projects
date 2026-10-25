import {
  CheckCircleFilled,
  ClockCircleOutlined,
  FileDoneOutlined,
  SyncOutlined,
  ToolOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Alert, Card, Empty, Spin, Steps, Tag, Tooltip, Typography } from 'antd';
import type { StepsProps } from 'antd';
import { useResultStore } from '../../stores/resultStore';
import { useTaskStore } from '../../stores/taskStore';
import {
  formatDateTime,
  formatStepLabel,
  getTaskStatusMeta,
  getToolLabel,
  isTaskActive,
} from '../../utils/format';

const { Text } = Typography;

const PHASES = [
  { title: '组装上下文', description: '读取会话历史与附件资料' },
  { title: '模型推理', description: '规划分析路径与工具调用' },
  { title: '工具执行', description: '查询数据、检索证据与生成文件' },
  { title: '生成结果', description: '汇总六部分结构化结论' },
  { title: '完成', description: '保存结果与上下文摘要' },
];

function resolvePhase(step: string): number {
  if (step.startsWith('llm_reasoning')) return 1;
  if (step.startsWith('tool_execution:')) return 2;
  if (
    step === 'result_generation' ||
    step === 'result_finalize' ||
    step === 'summary_compression'
  ) {
    return 3;
  }
  if (step === 'done') return 4;
  if (step === 'llm_error') return 1;
  if (step === 'timeout' || step === 'error') return 3;
  if (step === 'cancelled') return 4;
  return 0;
}

function getStepsItems(
  status: string | undefined,
  step: string | undefined,
): StepsProps['items'] {
  const current = resolvePhase(step ?? 'pending');
  return PHASES.map((phase, index) => {
    let itemStatus: 'wait' | 'process' | 'finish' | 'error' = 'wait';
    if (status === 'success') {
      itemStatus = 'finish';
    } else if (status === 'failed') {
      if (index < current) itemStatus = 'finish';
      else if (index === current) itemStatus = 'error';
    } else if (status === 'cancelled') {
      itemStatus = index < current ? 'finish' : 'wait';
    } else if (status === 'running') {
      if (index < current) itemStatus = 'finish';
      else if (index === current) itemStatus = 'process';
    } else if (status === 'queued') {
      itemStatus = 'wait';
    }
    return {
      title: (
        <span className={`task-step-title${index === current ? ' is-current' : ''}`}>
          {phase.title}
        </span>
      ),
      description: (
        <span className="task-step-description">
          {index === current && isTaskActive(status)
            ? formatStepLabel(step)
            : phase.description}
        </span>
      ),
      status: itemStatus,
      icon:
        status === 'cancelled' && index === current ? (
          <ClockCircleOutlined />
        ) : status === 'failed' && index === current ? (
          <WarningOutlined />
        ) : undefined,
    };
  });
}

function StatusTag({ status }: { status?: string | null }) {
  const meta = getTaskStatusMeta(status);
  const running = status === 'running';
  const icon = running ? (
    <SyncOutlined spin />
  ) : status === 'success' ? (
    <CheckCircleFilled />
  ) : status === 'failed' ? (
    <WarningOutlined />
  ) : status === 'queued' ? (
    <ClockCircleOutlined />
  ) : undefined;
  return (
    <Tag color={meta.color} icon={icon} bordered={false} className="task-status-tag">
      {meta.label}
    </Tag>
  );
}

export default function TaskPanel() {
  const task = useTaskStore((state) => state.task);
  const tools = useTaskStore((state) => state.tools);
  const resultReady = useTaskStore((state) => state.resultReady);
  const recovering = useTaskStore((state) => state.recovering);
  const lastError = useTaskStore((state) => state.lastError);
  const result = useResultStore((state) => state.result);

  if (!task) {
    return (
      <Card className="task-panel task-panel--empty" variant="borderless">
        <div className="task-empty">
          <div className="task-empty__icon">
            <SyncOutlined />
          </div>
          <div>
            <div className="task-empty__title">等待分析任务</div>
            <div className="task-empty__desc">
              发送问题后，这里将实时显示任务状态、执行步骤与工具过程。
            </div>
          </div>
        </div>
      </Card>
    );
  }

  const meta = getTaskStatusMeta(task.task_status);
  const resultFileReady = resultReady || Boolean(result?.result_file_path);
  const isFailed = task.task_status === 'failed';
  const errorText = lastError || task.error_message;

  return (
    <Card
      className="task-panel"
      variant="borderless"
      title={
        <div className="task-panel__heading">
          <span className="section-eyebrow">LIVE TASK</span>
          <span className="task-panel__title">实时分析</span>
        </div>
      }
      extra={
        <div className="task-panel__extra">
          <Text type="secondary" className="task-id">
            #{task.task_id}
          </Text>
          <StatusTag status={task.task_status} />
        </div>
      }
    >
      {recovering && (
        <div className="task-recovering">
          <Spin size="small" />
          <span>连接恢复中，正在重建任务进度…</span>
        </div>
      )}

      <div className="task-current-step">
        <span className={`status-dot status-dot--${meta.badgeStatus}`} />
        <div>
          <div className="task-current-step__label">{formatStepLabel(task.current_step)}</div>
          <div className="task-current-step__meta">
            开始于 {formatDateTime(task.started_at)}
            {task.finished_at ? ` · 结束于 ${formatDateTime(task.finished_at)}` : ''}
          </div>
        </div>
      </div>

      {errorText && (isFailed || lastError) && (
        <Alert
          className="task-error"
          type="error"
          showIcon
          message="任务异常"
          description={errorText}
        />
      )}

      <Steps
        direction="vertical"
        size="small"
        className="task-steps"
        items={getStepsItems(task.task_status, task.current_step)}
      />

      <div className="task-section">
        <div className="task-section__title">
          <ToolOutlined />
          <span>工具执行</span>
          <span className="task-section__count">{tools.length}</span>
        </div>
        {tools.length === 0 ? (
          <div className="task-tools-empty">暂无工具调用记录</div>
        ) : (
          <div className="task-tools">
            {tools.map((tool) => (
              <div className="task-tool-row" key={tool.key}>
                <span className={`task-tool-state is-${tool.status}`}>
                  {tool.status === 'running' ? <SyncOutlined spin /> : <CheckCircleFilled />}
                </span>
                <div className="task-tool-main">
                  <div className="task-tool-name">
                    {getToolLabel(tool.toolName)}
                    <code>{tool.toolName}</code>
                  </div>
                  {tool.summary && (
                    <Tooltip title={tool.summary}>
                      <div className="task-tool-summary">{tool.summary}</div>
                    </Tooltip>
                  )}
                </div>
                <Tag
                  bordered={false}
                  color={tool.status === 'running' ? 'processing' : 'success'}
                  className="task-tool-tag"
                >
                  {tool.status === 'running' ? '执行中' : '完成'}
                </Tag>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="task-file-row">
        <span className="task-file-label">
          <FileDoneOutlined /> 结果文件
        </span>
        {resultFileReady ? (
          <Tag color="success" bordered={false}>
            已生成
          </Tag>
        ) : task.task_status === 'failed' ? (
          <Tag color="error" bordered={false}>
            未生成
          </Tag>
        ) : task.task_status === 'cancelled' ? (
          <Tag bordered={false}>未生成</Tag>
        ) : (
          <Tag color="blue" bordered={false}>
            等待生成
          </Tag>
        )}
      </div>

      {!tools.length && !isTaskActive(task.task_status) && resultReady && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="结果文件已准备完成，请在下方查看分析结果"
          className="task-done-empty"
        />
      )}
    </Card>
  );
}
