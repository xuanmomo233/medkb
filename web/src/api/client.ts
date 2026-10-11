import { runMock } from '@/mocks/registry'

const TOKEN_KEY = 'medkb_token'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) ?? '',
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn }

type Query = Record<string, string | number | boolean | undefined | null | (string | number)[]>

export function buildQuery(q?: Query): string {
  if (!q) return ''
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === '' || v === false) continue
    p.set(k, Array.isArray(v) ? v.join(',') : String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

export async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
  const url = `/api${path}${buildQuery(opts.query)}`
  if (import.meta.env.VITE_MOCK === '1') {
    const hit = await runMock<T>(method, path, opts.query ?? {}, opts.body)
    if (hit.matched) return hit.data
  }
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers['X-Token'] = token
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(url, { method, headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) })
  } catch {
    throw new ApiError(0, '网络连接失败，请检查网络后重试')
  }
  if (res.status === 401 && path !== '/auth/login' && path !== '/auth/register') {
    tokenStore.clear()
    onUnauthorized?.()
    throw new ApiError(401, '登录已过期，请重新登录')
  }
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`
    try {
      const j = await res.json()
      msg = j.detail ?? j.message ?? msg
    } catch { /* 非 JSON 响应 */ }
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const get = <T>(path: string, query?: Query) => request<T>('GET', path, { query })
export const post = <T>(path: string, body?: unknown) => request<T>('POST', path, { body })
export const put = <T>(path: string, body?: unknown) => request<T>('PUT', path, { body })
export const del = <T>(path: string, query?: Query, body?: unknown) => request<T>('DELETE', path, { query, body })
