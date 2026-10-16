import { Button, Form, Input } from 'antd'
import { useNavigate } from 'react-router-dom'
import { register } from '../api/auth'
import { AuthLink, AuthShell } from '../components/AuthShell'

export default function RegisterPage() {
  const navigate = useNavigate()

  return (
    <AuthShell
      title="建立书斋"
      hint="创建账号后即可开始对话与上传知识"
      extra={
        <>
          已有账号？<AuthLink to="/login">去登录</AuthLink>
        </>
      }
    >
      <Form
        layout="vertical"
        onFinish={async (values) => {
          // 注册响应与登录响应结构一致，成功后直接进入工作台。
          await register(values)
          navigate('/chat', { replace: true })
        }}
      >
        <Form.Item
          label="用户名"
          name="username"
          rules={[
            { required: true, message: '请输入用户名' },
            { min: 2, message: '用户名至少 2 个字符' },
          ]}
        >
          <Input size="large" placeholder="至少 2 个字符" />
        </Form.Item>
        <Form.Item
          label="邮箱"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' },
          ]}
        >
          <Input size="large" placeholder="name@example.com" />
        </Form.Item>
        <Form.Item
          label="密码"
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 6, message: '密码至少 6 位' },
          ]}
        >
          <Input.Password size="large" placeholder="至少 6 位" />
        </Form.Item>
        <Button type="primary" htmlType="submit" size="large" block>
          注册并进入
        </Button>
      </Form>
    </AuthShell>
  )
}
