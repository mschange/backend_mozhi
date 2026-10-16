import type { ReactNode } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Switch } from 'antd'
import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { getAccessToken } from '../api/storage'
import { useThemeMode } from '../theme/ThemeProvider'

export function RequireAuth() {
  const location = useLocation()
  // 当前守卫只检查字符串是否存在，不解析 JWT，也不请求 /api/auth/me。
  if (!getAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}

export function GuestOnly() {
  // 已有 token 时不再展示登录/注册页；token 是否有效由后续 API 响应决定。
  if (getAccessToken()) {
    return <Navigate to="/chat" replace />
  }
  return <Outlet />
}

export function AuthShell({
  title,
  hint,
  children,
  extra,
}: {
  title: string
  hint: string
  children: ReactNode
  extra: ReactNode
}) {
  const { mode, toggle } = useThemeMode()
  return (
    <div className="auth-layout">
      <section className="auth-stage">
        <div>
          <p className="brand">
            墨知
            <small>MO ZHI · KNOWLEDGE ATELIER</small>
          </p>
        </div>
        <p className="auth-quote">把资料沉进墨色里，把答案从记忆中唤起。</p>
        <div style={{ color: 'var(--muted)', letterSpacing: '0.18em', fontSize: 12 }}>
          对话 · 知识库 · 长期记忆
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
            <Switch
              checked={mode === 'dark'}
              checkedChildren={<MoonOutlined />}
              unCheckedChildren={<SunOutlined />}
              onChange={() => toggle()}
            />
          </div>
          <h2>{title}</h2>
          <p className="hint">{hint}</p>
          {children}
          <div style={{ marginTop: 18, color: 'var(--muted)' }}>{extra}</div>
        </div>
      </section>
    </div>
  )
}

export function AuthLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to}>{children}</Link>
}
