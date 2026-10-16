const ACCESS_KEY = 'mozhi_access_token'
const REFRESH_KEY = 'mozhi_refresh_token'

// 路由守卫和请求层都通过同一函数读取，避免 key 字符串散落在组件中。
export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

// 当前只保存 refresh token，没有刷新 access token 的请求流程。
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function saveTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

// 退出和鉴权失败必须同时清除两个 token，避免留下错误的登录状态。
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}
