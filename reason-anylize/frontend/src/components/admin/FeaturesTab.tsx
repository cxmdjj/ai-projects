import { useEffect, useState } from 'react';
import {
  CheckCircleFilled,
  ControlOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Button,
  Spin,
  Switch,
  Tag,
  Typography,
} from 'antd';
import { adminApi } from '../../api/admin';
import { getErrorMessage } from '../../api/client';

const { Text, Paragraph } = Typography;

const FEATURE_META: Record<string, { label: string; description: string }> = {
  'feature.db_query': {
    label: '只读数据库查询',
    description: '允许分析助手执行只读 SQL 查询，获取业务数据证据。',
  },
  'feature.file_ops': {
    label: '文件读写',
    description: '允许读取与写入当前会话 workspace 中的文件。',
  },
  'feature.text_search': {
    label: '文本检索',
    description: '允许在附件与 workspace 文件中检索相关文本内容。',
  },
  'feature.command_exec': {
    label: '命令执行',
    description: '允许在沙箱中执行命令。开启前请确认隔离环境安全。',
  },
  'feature.result_file': {
    label: '结果文件生成',
    description: '允许生成可下载的分析结果文件与报告。',
  },
};

const DEFAULT_KEYS = Object.keys(FEATURE_META);

export default function FeaturesTab() {
  const { message } = AntdApp.useApp();
  const [features, setFeatures] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);

  const loadFeatures = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await adminApi.features();
      setFeatures(result.features ?? {});
    } catch (err) {
      setError(getErrorMessage(err, '功能开关加载失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadFeatures();
  }, []);

  const allKeys = Array.from(new Set([...DEFAULT_KEYS, ...Object.keys(features)]));

  const handleToggle = async (key: string, checked: boolean) => {
    const previous = features[key] ?? 'off';
    const next = checked ? 'on' : 'off';
    setFeatures((current) => ({ ...current, [key]: next }));
    setUpdatingKey(key);
    try {
      const result = await adminApi.updateFeature(key, checked ? 'on' : 'off');
      if (result.status !== 'updated') {
        throw new Error(result.message || '功能开关更新被拒绝');
      }
      setFeatures((current) => ({ ...current, [key]: result.config_value ?? next }));
      message.success(`${FEATURE_META[key]?.label ?? key} 已${checked ? '开启' : '关闭'}`);
    } catch (err) {
      setFeatures((current) => ({ ...current, [key]: previous }));
      message.error(getErrorMessage(err, '功能开关更新失败'));
    } finally {
      setUpdatingKey(null);
    }
  };

  return (
    <div className="admin-tab">
      <div className="admin-tab__toolbar">
        <div>
          <div className="admin-tab__title">功能开关</div>
          <Paragraph type="secondary" className="admin-tab__desc">
            控制分析助手可使用的工具。关闭后工具不再注入模型，执行请求也会被拒绝。
          </Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadFeatures()}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon message={error} className="admin-alert" />}

      <div className="feature-callout">
        <ControlOutlined />
        <span>开关变更会即时生效，仅影响后续新任务，不会中断正在运行的任务。</span>
      </div>

      <Spin spinning={loading}>
        <div className="feature-list">
          {allKeys.map((key) => {
            const meta = FEATURE_META[key] ?? {
              label: key,
              description: '自定义功能开关。',
            };
            const enabled = (features[key] ?? 'off') === 'on';
            return (
              <div className={`feature-row${enabled ? ' is-enabled' : ''}`} key={key}>
                <div className="feature-row__icon">
                  {enabled ? <CheckCircleFilled /> : <ControlOutlined />}
                </div>
                <div className="feature-row__body">
                  <div className="feature-row__title">
                    {meta.label}
                    <code>{key}</code>
                  </div>
                  <div className="feature-row__desc">{meta.description}</div>
                </div>
                <div className="feature-row__control">
                  <Tag bordered={false} color={enabled ? 'success' : 'default'}>
                    {enabled ? 'ON' : 'OFF'}
                  </Tag>
                  <Switch
                    checked={enabled}
                    loading={updatingKey === key}
                    disabled={updatingKey !== null && updatingKey !== key}
                    checkedChildren="开启"
                    unCheckedChildren="关闭"
                    onChange={(checked) => void handleToggle(key, checked)}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Spin>

      <Text type="secondary" className="feature-footnote">
        共 {allKeys.length} 项功能开关。所有开关统一保存在 system_configs 的 feature.* 配置下。
      </Text>
    </div>
  );
}
