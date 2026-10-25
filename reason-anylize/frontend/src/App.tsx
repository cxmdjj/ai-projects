import { useEffect, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuthStore } from './stores/authStore';
import LoginPage from './pages/LoginPage';
import CallbackPage from './pages/CallbackPage';
import WorkbenchPage from './pages/WorkbenchPage';
import AdminPage from './pages/AdminPage';

function FullPageLoading({ text = '正在加载…' }: { text?: string }) {
  return (
    <div className="full-page-loading">
      <div className="brand-mark brand-mark--large">析</div>
      <Spin size="large" />
      <span>{text}</span>
    </div>
  );
}

function RequireAuth({
  children,
  adminOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
}) {
  const user = useAuthStore((state) => state.user);
  const initialized = useAuthStore((state) => state.initialized);

  if (!initialized) {
    return <FullPageLoading text="正在确认登录状态…" />;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (adminOnly && user.role !== 'admin') {
    return <Navigate to="/workbench" replace />;
  }
  return <>{children}</>;
}

function HomeRedirect() {
  const user = useAuthStore((state) => state.user);
  const initialized = useAuthStore((state) => state.initialized);
  if (!initialized) return <FullPageLoading />;
  return <Navigate to={user ? '/workbench' : '/login'} replace />;
}

export default function App() {
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    // 授权回调页自行校验，避免重复消费/重复请求。
    if (window.location.pathname !== '/auth/callback') {
      void initialize();
    }
  }, [initialize]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<CallbackPage />} />
      <Route
        path="/workbench"
        element={
          <RequireAuth>
            <WorkbenchPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth adminOnly>
            <AdminPage />
          </RequireAuth>
        }
      />
      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
