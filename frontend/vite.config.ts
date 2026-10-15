import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 浏览器始终访问 5173；开发期由 Vite 保留 /api 前缀并转发给后端。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE 可能持续很久，开发代理不能按普通请求设置短超时。
        timeout: 0,
      },
    },
  },
})
