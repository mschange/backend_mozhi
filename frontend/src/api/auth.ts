import { client } from './client'
import type { AuthPayload, User } from '../types'
import { saveTokens } from './storage'

export async function register(payload: { username: string; email: string; password: string }) {
  const data = await client.post<AuthPayload, AuthPayload>('/api/auth/register', payload)
  // 注册成功即建立本地登录态，与登录流程保持一致。
  saveTokens(data.access_token, data.refresh_token)
  return data
}

export async function login(payload: { username: string; password: string }) {
  const data = await client.post<AuthPayload, AuthPayload>('/api/auth/login', payload)
  saveTokens(data.access_token, data.refresh_token)
  return data
}

// 当前页面没有调用该函数，但它是认证 API 的成品能力，保留供身份展示扩展。
export async function fetchMe() {
  return client.get<User, User>('/api/auth/me')
}
