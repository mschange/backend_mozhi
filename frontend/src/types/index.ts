// 登录/注册响应中的用户信息。
export type User = {
  id: string
  username: string
  email: string
  created_at?: string
}

// 后端同时返回 access 与 refresh token；当前成品只使用 access token 发请求。
export type AuthPayload = {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

// message_count 用于判断是否已有可复用的空会话。
export type Chat = {
  id: string
  title: string
  created_at?: string
  updated_at?: string
  message_count?: number
}

export type Citation = {
  source?: string
  snippet?: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | string
  content: string
  citations?: Citation[] | null
  created_at?: string
  // typing 仅存在于浏览器临时消息，用于控制流式光标。
  typing?: boolean
}

export type KnowledgeDoc = {
  id: string
  filename: string
  status: 'processing' | 'ready' | 'failed' | string
  error_message?: string | null
  created_at?: string
}
