import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Result, Spin } from 'antd';
import { getErrorMessage } from '../api/client';
import { useAuthStore } from '../stores/authStore';

type CallbackState = 'checking' | 'success' | 'error';

export default function CallbackPage() {
  const navigate = useNavigate();
  const fetchMe = useAuthStore((state) => state.fetchMe);
  const [state, setState] = useState<CallbackState>('checking');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const user = await fetchMe();
        if (!active) return;
        if (!user) {
          setError('登录状态无效，请重新登录。');
          setState('error');
          return;
        }
        setState('success');
        window.setTimeout(() => {
          if (active) navigate('/workbench', { replace: true });
        }, 450);
      } catch (err) {
        if (!active) return;
        setError(`${getErrorMessage(err, '登录失败或登录状态已过期')}，请返回登录页重试。`);
        setState('error');
      }
    })();
    return () => {
      active = false;
    };
  }, [fetchMe, navigate]);

  if (state === 'error') {
    return (
      <div className="callback-page">
        <div className="callback-card">
          <Result
            status="error"
            title="登录未完成"
            subTitle={error || '登录失败或登录状态已过期。'}
            extra={[
              <Button
                type="primary"
                key="login"
                onClick={() => {
                  window.location.href = '/login';
                }}
              >
                返回登录
              </Button>,
              <Button
                key="retry"
                onClick={() => {
                  window.location.href = '/auth/login';
                }}
              >
                重新授权
              </Button>,
            ]}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="callback-page">
      <div className="callback-card callback-card--loading">
        <div className="brand-mark brand-mark--large">析</div>
        <Spin size="large" />
        <div className="callback-title">
          {state === 'success' ? '登录成功，正在进入工作台…' : '正在校验登录状态…'}
        </div>
        <div className="callback-subtitle">请稍候，不要关闭当前页面</div>
      </div>
    </div>
  );
}
