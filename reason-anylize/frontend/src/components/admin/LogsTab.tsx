import { useCallback, useEffect, useRef, useState } from 'react';
import { ReloadOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { adminApi } from '../../api/admin';
import { getErrorMessage } from '../../api/client';
import { formatDateTime } from '../../utils/format';

const { Text } = Typography;

export default function LogsTab() {
  const [logs, setLogs] = useState('');
  const [lineCount, setLineCount] = useState(0);
  const [lines, setLines] = useState(200);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const loadingRef = useRef(false);
  const logRef = useRef<HTMLPreElement>(null);

  const loadLogs = useCallback(
    async (showSpinner = true) => {
      if (loadingRef.current) return;
      loadingRef.current = true;
      if (showSpinner) setLoading(true);
      setError(null);
      try {
        const result = await adminApi.logs(lines);
        setLogs(result.logs);
        setLineCount(result.lines);
        setUpdatedAt(new Date().toISOString());
      } catch (err) {
        setError(getErrorMessage(err, '运行日志加载失败'));
      } finally {
        loadingRef.current = false;
        setLoading(false);
      }
    },
    [lines],
  );

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => {
      void loadLogs(false);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadLogs]);

  useEffect(() => {
    const element = logRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [logs]);

  return (
    <div className="admin-tab">
      <div className="admin-tab__toolbar">
        <div>
          <div className="admin-tab__title">运行日志</div>
          <Typography.Paragraph type="secondary" className="admin-tab__desc">
            实时查看后端运行日志尾部，用于排查任务执行和接口异常。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Select
            value={lines}
            onChange={setLines}
            options={[
              { value: 100, label: '最近 100 行' },
              { value: 200, label: '最近 200 行' },
              { value: 500, label: '最近 500 行' },
              { value: 1000, label: '最近 1000 行' },
            ]}
            style={{ width: 140 }}
          />
          <Space size={6} className="auto-refresh-switch">
            <Switch
              checked={autoRefresh}
              onChange={setAutoRefresh}
              size="small"
              checkedChildren="自动"
              unCheckedChildren="手动"
            />
            <Text type="secondary">每 5 秒</Text>
          </Space>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => void loadLogs()}
          >
            刷新
          </Button>
        </Space>
      </div>

      {error && <Alert type="error" showIcon message={error} className="admin-alert" />}

      <div className="logs-meta">
        <Space size={12} wrap>
          <Tag bordered={false} color="blue">
            app.log
          </Tag>
          <Text type="secondary">加载 {lineCount} 行</Text>
          <Text type="secondary">最后更新：{formatDateTime(updatedAt)}</Text>
        </Space>
        {loading && <Spin size="small" />}
      </div>

      <div className="log-console-wrap">
        <div className="log-console-bar">
          <span className="console-dot console-dot--red" />
          <span className="console-dot console-dot--yellow" />
          <span className="console-dot console-dot--green" />
          <span className="log-console-title">backend / app.log</span>
        </div>
        <pre className="log-console" ref={logRef}>
          {logs || '(暂无日志内容)'}
        </pre>
      </div>
    </div>
  );
}
