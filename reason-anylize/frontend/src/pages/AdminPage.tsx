import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeftOutlined,
  ControlOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LogoutOutlined,
  SettingOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Avatar, Button, Tabs, Tag, Tooltip, Typography } from 'antd';
import ConfigTab from '../components/admin/ConfigTab';
import DataSourceTab from '../components/admin/DataSourceTab';
import FeaturesTab from '../components/admin/FeaturesTab';
import LogsTab from '../components/admin/LogsTab';
import { useAuthStore } from '../stores/authStore';
import { useConversationStore } from '../stores/conversationStore';
import { roleLabel } from '../utils/format';

const { Text } = Typography;

type AdminTabKey = 'configs' | 'logs' | 'datasources' | 'features';

export default function AdminPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const clearConversations = useConversationStore((state) => state.clear);
  const [activeTab, setActiveTab] = useState<AdminTabKey>('configs');

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // 本地状态仍会在 finally 中清理。
    }
    clearConversations();
    navigate('/login', { replace: true });
  };

  const displayName = user?.display_name || user?.username || '管理员';

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-header__brand">
          <button
            type="button"
            className="brand-button"
            onClick={() => navigate('/workbench')}
            aria-label="返回工作台"
          >
            <div className="brand-mark">析</div>
            <div className="brand-copy">
              <span className="brand-copy__name">经营归因分析</span>
              <span className="brand-copy__sub">ADMIN CONSOLE</span>
            </div>
          </button>
          <div className="header-divider" />
          <Tag icon={<SafetyCertificateOutlined />} color="purple" bordered={false} className="admin-mode-tag">
            管理端
          </Tag>
        </div>

        <div className="admin-header__actions">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/workbench')}>
            返回工作台
          </Button>
          <div className="header-user">
            <Avatar className="header-avatar header-avatar--admin" size={32}>
              {displayName.slice(0, 1)}
            </Avatar>
            <div className="header-user__copy">
              <span className="header-user__name">{displayName}</span>
              <span className="header-user__role">{roleLabel(user?.role ?? '')}</span>
            </div>
          </div>
          <Tooltip title="退出登录">
            <Button type="text" icon={<LogoutOutlined />} onClick={() => void handleLogout()}>
              退出
            </Button>
          </Tooltip>
        </div>
      </header>

      <main className="admin-main">
        <section className="admin-hero">
          <div>
            <Text className="section-eyebrow">SYSTEM ADMINISTRATION</Text>
            <h1 className="admin-hero__title">系统管理控制台</h1>
            <p className="admin-hero__desc">
              维护模型与运行配置、查看服务日志、验证数据源连接并管理分析功能开关。
            </p>
          </div>
          <div className="admin-hero__badge">
            <SafetyCertificateOutlined />
            <span>管理员权限</span>
          </div>
        </section>

        <section className="admin-card">
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as AdminTabKey)}
            className="admin-tabs"
            items={[
              {
                key: 'configs',
                label: (
                  <span>
                    <SettingOutlined /> 系统配置
                  </span>
                ),
                children: <ConfigTab />,
              },
              {
                key: 'logs',
                label: (
                  <span>
                    <FileTextOutlined /> 运行日志
                  </span>
                ),
                children: <LogsTab />,
              },
              {
                key: 'datasources',
                label: (
                  <span>
                    <DatabaseOutlined /> 数据源
                  </span>
                ),
                children: <DataSourceTab />,
              },
              {
                key: 'features',
                label: (
                  <span>
                    <ControlOutlined /> 功能开关
                  </span>
                ),
                children: <FeaturesTab />,
              },
            ]}
          />
        </section>
      </main>
    </div>
  );
}
