import axios, { AxiosError } from 'axios'
import { message } from 'antd'
import { clearTokens, getAccessToken } from './storage'

// 业务错误与 HTTP 错误统一成带 code 的异常，页面无需理解 AxiosError 结构。
export class ApiError extends Error {
  code: number
  constructor(code: number, msg: string) {
    super(msg)
    this.code = code
  }
}

export const client = axios.create({
  // 空字符串表示同源；生产环境可给普通请求配置公开的 API 基地址。
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 120000,
})

client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    // access token 只放在 Authorization 头，不拼进 URL，减少日志和历史记录泄漏。
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => {
    const payload = response.data as { code?: number; message?: string; data?: unknown }
    if (payload && typeof payload.code === 'number') {
      // 后端普通接口使用统一信封；成功时只把 data 交给业务层。
      if (payload.code === 0) {
        return payload.data as never
      }
      if (payload.code === 40100 || payload.code === 40101 || payload.code === 40102) {
        clearTokens()
        // 用整页跳转清空可能仍持有旧身份状态的 React 树。
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
      }
      if (!response.config.skipErrorToast) {
        message.error(payload.message || '请求失败')
      }
      throw new ApiError(payload.code, payload.message || '请求失败')
    }
    // 非信封响应保持原样，兼容返回普通 JSON 的端点。
    return response.data
  },
  (error: AxiosError<{ code?: number; message?: string }>) => {
    const status = error.response?.status
    const code = error.response?.data?.code
    const msg = error.response?.data?.message || error.message || '网络异常'
    if (status === 401 || code === 40100 || code === 40101 || code === 40102) {
      clearTokens()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    if (!error.config?.skipErrorToast) {
      message.error(msg)
    }
    // 错误码优先使用业务码，其次 HTTP 状态，最后使用通用码。
    throw new ApiError(code || status || 50000, msg)
  },
)

// 上传页需要关闭拦截器 toast，由页面根据文档状态展示一次更准确的错误。
declare module 'axios' {
  interface AxiosRequestConfig {
    skipErrorToast?: boolean
  }
}
