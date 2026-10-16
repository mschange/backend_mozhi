import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { App as AntdApp, ConfigProvider, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'

export type ThemeMode = 'dark' | 'light'

type ThemeContextValue = {
  mode: ThemeMode
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'dark',
  toggle: () => undefined,
})

const STORAGE_KEY = 'mozhi-theme'

function readMode(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY)
  // 仅显式 light 进入亮色；缺省值和异常值统一回到暗色基线。
  return saved === 'light' ? 'light' : 'dark'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readMode)

  useEffect(() => {
    // HTML 属性驱动 Less 中的 CSS 变量，localStorage 保证刷新后模式不丢失。
    document.documentElement.setAttribute('data-theme', mode)
    localStorage.setItem(STORAGE_KEY, mode)
  }, [mode])

  const value = useMemo(
    () => ({
      mode,
      toggle: () => setMode((prev) => (prev === 'dark' ? 'light' : 'dark')),
    }),
    [mode],
  )

  const theme = {
    // CSS 变量控制自定义区域，Ant Design 算法控制组件，两者必须同步切换。
    algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: '#c9a227',
      colorInfo: '#5aae9b',
      borderRadius: 10,
      fontFamily: "'Noto Sans SC', 'PingFang SC', sans-serif",
    },
    components: {
      Layout: {
        bodyBg: 'transparent',
        headerBg: 'transparent',
        siderBg: 'transparent',
      },
      Button: { fontWeight: 600 },
    },
  }

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider locale={zhCN} theme={theme}>
        {/* AntdApp 提供 message 上下文，并限制同时展示的提示数量。 */}
        <AntdApp message={{ maxCount: 3 }}>{children}</AntdApp>
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}

export function useThemeMode() {
  return useContext(ThemeContext)
}
