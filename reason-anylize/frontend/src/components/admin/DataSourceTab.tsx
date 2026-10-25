import { useEffect, useState } from 'react';
import {
  ApiOutlined,
  DatabaseOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App as AntdApp,
  Button,
  Descriptions,
  Input,
  Select,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { adminApi } from '../../api/admin';
import { getErrorMessage } from '../../api/client';
import type { DataSourceInfo } from '../../types/api';

const { Text, Paragraph } = Typography;

export default function DataSourceTab() {
  const { message } = AntdApp.useApp();
  const [info, setInfo] = useState<DataSourceInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dbType, setDbType] = useState('sqlite');
  const [conn, setConn] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const loadInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await adminApi.datasources();
      setInfo(result);
      setDbType(result.current.type || 'sqlite');
      setConn(result.current.conn || '');
    } catch (err) {
      setError(getErrorMessage(err, '数据源信息加载失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadInfo();
  }, []);

  const handleTest = async () => {
    if (!conn.trim()) {
      message.warning('请填写连接信息');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await adminApi.testDataSource(dbType, conn.trim());
      setTestResult(result);
      if (result.ok) message.success(result.message || '连接成功');
      else message.error(result.message || '连接失败');
    } catch (err) {
      const text = getErrorMessage(err, '连接测试失败');
      setTestResult({ ok: false, message: text });
      message.error(text);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="admin-tab">
      <div className="admin-tab__toolbar">
        <div>
          <div className="admin-tab__title">数据源</div>
          <Paragraph type="secondary" className="admin-tab__desc">
            查看当前分析数据源，并测试新的数据库连接。测试不会切换数据源。
          </Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadInfo()}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon message={error} className="admin-alert" />}

      <Spin spinning={loading}>
        <section className="datasource-section">
          <div className="datasource-section__title">
            <DatabaseOutlined />
            当前数据源
          </div>
          <Descriptions
            bordered
            column={1}
            size="small"
            className="datasource-descriptions"
            styles={{ label: { width: 130 } }}
          >
            <Descriptions.Item label="数据库类型">
              <Tag color="blue" bordered={false}>
                {(info?.current.type || '—').toUpperCase()}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="连接信息">
              <code className="datasource-value">{info?.current.conn || '—'}</code>
            </Descriptions.Item>
            <Descriptions.Item label="DATABASE_URL">
              <code className="datasource-value">{info?.database_url || '—'}</code>
            </Descriptions.Item>
          </Descriptions>
        </section>
      </Spin>

      <section className="datasource-section">
        <div className="datasource-section__title">
          <ApiOutlined />
          连接测试
        </div>
        <div className="datasource-form">
          <div className="datasource-field">
            <label htmlFor="db-type">数据库类型</label>
            <Select
              id="db-type"
              value={dbType}
              onChange={(value) => {
                setDbType(value);
                setTestResult(null);
              }}
              options={[
                { value: 'sqlite', label: 'SQLite' },
                { value: 'mysql', label: 'MySQL' },
              ]}
              style={{ width: '100%' }}
            />
          </div>
          <div className="datasource-field datasource-field--wide">
            <label htmlFor="db-conn">连接信息</label>
            <Input
              id="db-conn"
              value={conn}
              onChange={(event) => {
                setConn(event.target.value);
                setTestResult(null);
              }}
              placeholder={
                dbType === 'sqlite'
                  ? '例如 ./data/app.db 或 sqlite:///./data/app.db'
                  : '例如 mysql+pymysql://user:password@host:3306/database'
              }
            />
            <Text type="secondary" className="datasource-help">
              {dbType === 'sqlite'
                ? '支持填写文件路径，系统会自动补齐 sqlite:/// 前缀。'
                : '请填写完整的 SQLAlchemy MySQL 连接串。'}
            </Text>
          </div>
          <div className="datasource-field datasource-field--action">
            <Button type="primary" loading={testing} onClick={() => void handleTest()}>
              测试连接
            </Button>
          </div>
        </div>

        {testResult && (
          <Alert
            className="datasource-result"
            type={testResult.ok ? 'success' : 'error'}
            showIcon
            message={testResult.ok ? '连接成功' : '连接失败'}
            description={testResult.message}
          />
        )}
      </section>

      <Alert
        type="info"
        showIcon
        className="datasource-note"
        message="切换数据源需要修改后端环境变量 DATABASE_URL 并重启服务"
        description="本页仅用于验证连接可用性，不会修改运行时数据源，也不会影响已有分析记录。"
      />
    </div>
  );
}
