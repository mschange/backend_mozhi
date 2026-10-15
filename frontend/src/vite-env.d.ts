/// <reference types="vite/client" />

// 这里只声明公开的 API 基地址；VITE_ 变量会进入浏览器包，绝不能放密钥。
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
