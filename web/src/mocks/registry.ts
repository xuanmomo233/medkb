// mock 注册表：开发期（VITE_MOCK=1）后端未就绪时由各功能模块自带 mock。
// 每个功能在 src/mocks/<feature>.mock.ts 中调用 registerMock 注册，无需修改共享文件。

type Handler = (ctx: { query: Record<string, unknown>; body: unknown; params: Record<string, string> }) => unknown | Promise<unknown>
interface Entry { method: string; re: RegExp; keys: string[]; handler: Handler }

const entries: Entry[] = []

export function registerMock(method: string, pattern: string, handler: Handler) {
  const keys: string[] = []
  const re = new RegExp('^' + pattern.replace(/\{(\w+)\}/g, (_, k) => { keys.push(k); return '([^/]+)' }) + '$')
  entries.push({ method: method.toUpperCase(), re, keys, handler })
}

export const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))

/** handler 返回 NEXT 表示"不是我的"，继续匹配后续同路径 mock（如 /progress/mark 按 target_type 分担） */
export const NEXT = Symbol('mock-next')

export async function runMock<T>(method: string, path: string, query: Record<string, unknown>, body: unknown):
  Promise<{ matched: true; data: T } | { matched: false }> {
  for (const e of entries) {
    if (e.method !== method.toUpperCase()) continue
    const m = e.re.exec(path)
    if (!m) continue
    const params: Record<string, string> = {}
    e.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]) })
    const data = await e.handler({ query, body, params })
    if (data === NEXT) continue
    await delay()
    return { matched: true, data: data as T }
  }
  return { matched: false }
}
