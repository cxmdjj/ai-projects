import { useEffect, useState } from 'react';
import {
  EditOutlined,
  ReloadOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Button,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { adminApi } from '../../api/admin';
import { getErrorMessage } from '../../api/client';
import type { SystemConfigItem } from '../../types/api';
import { formatDateTime } from '../../utils/format';

const { Text, Paragraph } = Typography;

const groupColors: Record<string, string> = {
  llm: 'purple',
  feature: 'blue',
  analysis: 'cyan',
  datasource: 'geekblue',
  sandbox: 'orange',
};

const groupLabels: Record<string, string> = {
  llm: '模型',
  feature: '功能开关',
  analysis: '分析参数',
  datasource: '数据源',
  sandbox: '沙箱',
};

export default function ConfigTab() {
  const { message } = AntdApp.useApp();
  const [configs, setConfigs] = useState<SystemConfigItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<SystemConfigItem | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');

  const loadConfigs = async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const items = await adminApi.configs();
      setConfigs(items);
    } catch (err) {
      setError(getErrorMessage(err, '系统配置加载失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadConfigs();
  }, []);

  const handleReload = async () => {
    setReloading(true);
    try {
      const result = await adminApi.reload();
      message.success(result.message || '配置已重载');
      await loadConfigs(false);
    } catch (err) {
      message.error(getErrorMessage(err, '配置重载失败'));
    } finally {
      setReloading(false);
    }
  };

  const openEdit = (config: SystemConfigItem) => {
    setEditing(config);
    setEditValue(config.config_value);
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await adminApi.updateConfig(editing.config_key, editValue);
      setConfigs((current) =>
        current.map((item) =>
          item.config_key === editing.config_key
            ? { ...item, config_value: editValue, updated_at: new Date().toISOString() }
            : item,
        ),
      );
      message.success('配置已保存并立即生效');
      setEditing(null);
    } catch (err) {
      message.error(getErrorMessage(err, '配置保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const filtered = search.trim()
    ? configs.filter((item) => {
        const keyword = search.trim().toLowerCase();
        return (
          item.config_key.toLowerCase().includes(keyword) ||
          item.config_group.toLowerCase().includes(keyword) ||
          item.config_value.toLowerCase().includes(keyword)
        );
      })
    : configs;

  const columns: ColumnsType<SystemConfigItem> = [
    {
      title: '分组',
      dataIndex: 'config_group',
      key: 'config_group',
      width: 110,
      render: (group: string) => (
        <Tag color={groupColors[group] ?? 'default'} bordered={false}>
          {groupLabels[group] ?? group}
        </Tag>
      ),
      filters: Array.from(new Set(configs.map((item) => item.config_group))).map((group) => ({
        text: groupLabels[group] ?? group,
        value: group,
      })),
      onFilter: (value, record) => record.config_group === value,
    },
    {
      title: '配置键',
      dataIndex: 'config_key',
      key: 'config_key',
      width: 240,
      render: (key: string) => <code className="config-key">{key}</code>,
    },
    {
      title: '配置值',
      dataIndex: 'config_value',
      key: 'config_value',
      ellipsis: true,
      render: (value: string) => (
        <Tooltip title={value || '(空)'}>
          <span className={`config-value${value ? '' : ' is-empty'}`}>
            {value || '(空)'}
          </span>
        </Tooltip>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 155,
      render: (value: string) => <span className="table-muted">{formatDateTime(value)}</span>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 86,
      align: 'right',
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={() => openEdit(record)}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <div className="admin-tab">
      <div className="admin-tab__toolbar">
        <div>
          <div className="admin-tab__title">系统配置</div>
          <Paragraph type="secondary" className="admin-tab__desc">
            修改后立即写入运行时配置，无需重启服务。密钥类配置请谨慎操作。
          </Paragraph>
        </div>
        <Space wrap>
          <Input.Search
            allowClear
            placeholder="搜索配置键或值"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            style={{ width: 220 }}
          />
          <Button
            icon={<SyncOutlined />}
            onClick={() => void loadConfigs()}
            loading={loading}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={reloading}
            onClick={() => void handleReload()}
          >
            配置重载
          </Button>
        </Space>
      </div>

      {error && <Alert type="error" showIcon message={error} className="admin-alert" />}

      <Table<SystemConfigItem>
        className="admin-table"
        rowKey="config_key"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        size="middle"
        pagination={{ pageSize: 12, showSizeChanger: false, showTotal: (total) => `共 ${total} 项` }}
        scroll={{ x: 780 }}
        locale={{ emptyText: '暂无配置项' }}
      />

      <div className="config-hint">
        <Text type="secondary">
          当前共 {configs.length} 项配置。「配置重载」会从数据库重新载入全部配置到内存。
        </Text>
      </div>

      <Modal
        title="编辑配置"
        open={editing !== null}
        onCancel={() => {
          if (!saving) setEditing(null);
        }}
        onOk={() => void handleSave()}
        okText="保存并生效"
        cancelText="取消"
        confirmLoading={saving}
        destroyOnHidden
        width={620}
      >
        {editing && (
          <div className="config-edit">
            <div className="config-edit__key">
              <span>配置键</span>
              <code>{editing.config_key}</code>
            </div>
            <div className="config-edit__group">
              分组：{groupLabels[editing.config_group] ?? editing.config_group}
            </div>
            <Input.TextArea
              value={editValue}
              onChange={(event) => setEditValue(event.target.value)}
              autoSize={{ minRows: 3, maxRows: 10 }}
              placeholder="输入配置值"
              className="config-edit__input"
            />
            <Text type="secondary" className="config-edit__hint">
              保存后立即生效。留空表示使用环境变量或系统默认值（视配置项而定）。
            </Text>
          </div>
        )}
      </Modal>
    </div>
  );
}
