import dayjs from 'dayjs';

export function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : value;
}

export function formatFileSize(bytes?: number | null): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function formatRelativeTime(value?: string | null): string {
  if (!value) return '';
  const date = dayjs(value);
  if (!date.isValid()) return '';
  const now = dayjs();
  if (date.isSame(now, 'day')) return date.format('HH:mm');
  if (date.isSame(now.subtract(1, 'day'), 'day')) return '昨天';
  if (date.isSame(now, 'year')) return date.format('MM-DD');
  return date.format('YYYY-MM-DD');
}

export interface TaskStatusMeta {
  label: string;
  color: string;
  badgeStatus: 'success' | 'processing' | 'default' | 'error' | 'warning';
}

export const TASK_STATUS_META: Record<string, TaskStatusMeta> = {
  queued: { label: '排队中', color: 'blue', badgeStatus: 'default' },
  running: { label: '分析中', color: 'processing', badgeStatus: 'processing' },
  success: { label: '已完成', color: 'success', badgeStatus: 'success' },
  failed: { label: '失败', color: 'error', badgeStatus: 'error' },
  cancelled: { label: '已取消', color: 'default', badgeStatus: 'default' },
};

export function getTaskStatusMeta(status?: string | null): TaskStatusMeta {
  return (
    TASK_STATUS_META[status ?? ''] ?? {
      label: status || '未知',
      color: 'default',
      badgeStatus: 'default',
    }
  );
}

export const TOOL_LABELS: Record<string, string> = {
  db_query: '数据库查询',
  file_read: '读取文件',
  file_write: '写入文件',
  file_list: '文件列表',
  text_search: '文本检索',
  command_exec: '命令执行',
  result_file: '生成结果文件',
  submit_analysis_result: '提交分析结果',
};

export function getToolLabel(name?: string | null): string {
  if (!name) return '工具';
  return TOOL_LABELS[name] ?? name;
}

export function formatStepLabel(step?: string | null): string {
  if (!step) return '等待开始';
  if (step.startsWith('llm_reasoning')) {
    const round = step.split(':')[1];
    return round ? `模型推理 · 第 ${round} 轮` : '模型推理';
  }
  if (step.startsWith('tool_execution:')) {
    return `执行工具 · ${getToolLabel(step.split(':')[1])}`;
  }
  const labels: Record<string, string> = {
    pending: '等待调度',
    context_assembly: '组装分析上下文',
    result_generation: '生成结构化结果',
    result_finalize: '整理分析结果',
    summary_compression: '压缩上下文摘要',
    done: '分析完成',
    cancelled: '任务已取消',
    timeout: '任务超时',
    llm_error: '模型调用失败',
    error: '执行异常',
  };
  return labels[step] ?? step;
}

export function isTaskActive(status?: string | null): boolean {
  return status === 'queued' || status === 'running';
}

export function isTaskTerminal(status?: string | null): boolean {
  return status === 'success' || status === 'failed' || status === 'cancelled';
}

export function roleLabel(role: string): string {
  if (role === 'admin') return '系统管理员';
  if (role === 'analyst') return '分析用户';
  return role;
}

export function confidenceMeta(confidence?: string): { color: string; label: string } {
  switch (confidence) {
    case 'high':
      return { color: 'green', label: '高置信' };
    case 'medium':
      return { color: 'orange', label: '中置信' };
    case 'low':
      return { color: 'default', label: '低置信' };
    default:
      return { color: 'default', label: confidence || '未知' };
  }
}
