import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'medkb_theme'

function initial(): Theme {
  const saved = localStorage.getItem(KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

let current: Theme = initial()
const listeners = new Set<() => void>()
document.documentElement.dataset.theme = current

function setTheme(t: Theme) {
  current = t
  localStorage.setItem(KEY, t)
  document.documentElement.dataset.theme = t
  listeners.forEach((l) => l())
}

const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l) } }

/** 全应用共享的主题状态（顶栏按钮与设置页同步） */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => current)
  return { theme, toggle: () => setTheme(current === 'dark' ? 'light' : 'dark'), set: setTheme }
}

/** 阅读字号（题干/解析/卡片正文），范围 13~22 */
const FONT_KEY = 'medkb_reading_size'
export function getReadingSize(): number { return Number(localStorage.getItem(FONT_KEY)) || 16 }
export function setReadingSize(px: number) {
  localStorage.setItem(FONT_KEY, String(px))
  document.documentElement.style.setProperty('--reading-size', `${px}px`)
}
export function applyReadingSize() { setReadingSize(getReadingSize()) }
