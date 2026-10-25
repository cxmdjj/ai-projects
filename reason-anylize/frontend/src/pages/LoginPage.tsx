import {
  ArrowRightOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  LineChartOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Button, Divider, Tag, Typography } from 'antd';

const { Title, Paragraph, Text } = Typography;

const capabilities = [
  {
    icon: <LineChartOutlined />,
    title: '多轮归因',
    description: '围绕同一经营问题持续追问、补充证据与迭代结论',
  },
  {
    icon: <DatabaseOutlined />,
    title: '数据联动',
    description: '数据库查询、附件检索与文件工具协同完成分析',
  },
  {
    icon: <FileSearchOutlined />,
    title: '结果沉淀',
    description: '结构化六部分结果、证据链、报告导出与历史回放',
  },
];

export default function LoginPage() {
  const handleLogin = () => {
    // 必须使用浏览器跳转以跟随后端 302 到认证中心，不能使用 axios。
    window.location.href = '/auth/login';
  };

  return (
    <div className="login-page">
      <div className="login-orbit login-orbit--one" />
      <div className="login-orbit login-orbit--two" />
      <div className="login-shell">
        <section className="login-intro">
          <div className="login-brand">
            <div className="brand-mark brand-mark--large">析</div>
            <div>
              <Text className="login-brand-en">REASON WORKSPACE</Text>
              <div className="login-brand-name">经营归因分析系统</div>
            </div>
          </div>

          <Title className="login-hero-title" level={1}>
            让每一个经营问题，
            <br />
            都有证据链可循。
          </Title>
          <Paragraph className="login-hero-desc">
            面向经营分析场景的多轮智能工作台。连接业务数据，执行分析工具，持续追问，
            最终形成可追溯、可导出的结构化归因结论。
          </Paragraph>

          <div className="login-capabilities">
            {capabilities.map((item) => (
              <div className="login-capability" key={item.title}>
                <span className="login-capability-icon">{item.icon}</span>
                <div>
                  <div className="login-capability-title">{item.title}</div>
                  <div className="login-capability-desc">{item.description}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="login-trust">
            <SafetyCertificateOutlined />
            <span>统一身份认证 · 会话级数据隔离 · 分析过程全程留痕</span>
          </div>
        </section>

        <section className="login-card">
          <div className="login-card-lock">
            <LockOutlined />
          </div>
          <Title level={3} className="login-card-title">
            登录分析工作台
          </Title>
          <Paragraph type="secondary" className="login-card-subtitle">
            使用认证中心账号完成授权后即可开始分析。
          </Paragraph>

          <Button
            type="primary"
            size="large"
            block
            className="login-primary-button"
            onClick={handleLogin}
            icon={<ArrowRightOutlined />}
            iconPosition="end"
          >
            授权登录
          </Button>

          <div className="login-security-note">
            <LockOutlined />
            登录凭据由统一认证中心校验，本系统不保存你的密码。
          </div>

          <Divider plain className="login-divider">
            测试账号
          </Divider>

          <div className="login-accounts">
            <div className="login-account-row">
              <div className="login-account-role">
                <Tag color="blue">分析用户</Tag>
              </div>
              <div className="login-account-info">
                <Text code>analyst1</Text>
                <span className="login-account-sep">/</span>
                <Text type="secondary">analyst123</Text>
              </div>
            </div>
            <div className="login-account-row">
              <div className="login-account-role">
                <Tag color="purple">系统管理员</Tag>
              </div>
              <div className="login-account-info">
                <Text code>admin1</Text>
                <span className="login-account-sep">/</span>
                <Text type="secondary">admin123</Text>
              </div>
            </div>
          </div>

          <div className="login-footer">经营归因分析系统 · 内部数据分析平台</div>
        </section>
      </div>
    </div>
  );
}
