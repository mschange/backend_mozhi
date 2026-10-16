import { Button, Form, Input } from 'antd'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import { AuthLink, AuthShell } from '../components/AuthShell'

export default function LoginPage() {
  const navigate = useNavigate()

  return (
    <AuthShell
      title="欢迎回来"
      hint="使用用户名或邮箱登录墨知"
      extra={
        <>
          还没有账号？<AuthLink to="/register">去注册</AuthLink>
        </>
      }
    >
      <Form
        layout="vertical"
        onFinish={async (values) => {
          // API 成功时已经保存 token；replace 防止返回键回到登录表单。
          await login(values)
          navigate('/chat', { replace: true })
        }}
      >
        <Form.Item
          label="用户名 / 邮箱"
          name="username"
          rules={[{ required: true, message: '请输入用户名或邮箱' }]}
        >
          <Input size="large" placeholder="请输入用户名或邮箱" />
        </Form.Item>
        <Form.Item
          label="密码"
          name="password"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input.Password size="large" placeholder="请输入密码" />
        </Form.Item>
        <Button type="primary" htmlType="submit" size="large" block>
          登录
        </Button>
      </Form>
    </AuthShell>
  )
}
