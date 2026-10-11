import type { FacetLevel, QuizFilter, QuizMode, QuizQuery } from '@/api/types'

export const LETTERS = 'ABCDEFGH'

export const FACET_LEVELS: { key: FacetLevel; label: string }[] = [
  { key: 'bank_group', label: '题库系' },
  { key: 'bank', label: '来源题库' },
  { key: 'subject_dir', label: '学科' },
  { key: 'system', label: '系统' },
  { key: 'chapter', label: '章节' },
  { key: 'qtype', label: '题型' },
]

export const MODES: { value: QuizMode; label: string; desc: string }[] = [
  { value: 'practice', label: '练习', desc: '点选即判，立刻看解析' },
  { value: 'recite', label: '背题', desc: '直接显示答案与解析' },
  { value: 'quick', label: '快刷', desc: '答对自动下一题' },
  { value: 'test', label: '测试', desc: '全部答完统一交卷' },
]

const FLAGS = ['starred', 'wrong', 'due', 'random', 'shuffle'] as const

export interface RunParams { query: QuizQuery; mode: QuizMode; title: string; mins: number }

const truthy = (v: string | null) => v === '1' || v === 'true'

export function filterFromParams(sp: URLSearchParams): QuizFilter {
  const f: QuizFilter = {}
  for (const { key } of FACET_LEVELS) {
    const v = sp.get(key)
    if (v) f[key] = v
  }
  return f
}

export function parseRun(sp: URLSearchParams): RunParams {
  const query: QuizQuery = filterFromParams(sp)
  const ids = sp.get('ids')
  if (ids) query.ids = ids.split(',').map(Number).filter(Boolean)
  const day = Number(sp.get('plan_day'))
  if (day) query.plan_day = day
  const limit = Number(sp.get('limit'))
  if (limit) query.limit = limit
  for (const k of FLAGS) if (truthy(sp.get(k))) query[k] = true
  const m = sp.get('mode')
  const mode = MODES.some((x) => x.value === m) ? (m as QuizMode) : 'practice'
  return { query, mode, title: sp.get('title') ?? '', mins: Math.max(0, Number(sp.get('mins')) || 0) }
}

export function toSearch(o: object): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(o)) {
    if (v === undefined || v === null || v === '' || v === false || v === 0) continue
    p.set(k, v === true ? '1' : Array.isArray(v) ? v.join(',') : String(v))
  }
  return p.toString()
}

export function hashStr(s: string): string {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  return (h >>> 0).toString(36)
}

export function readJson<T>(store: Storage, key: string): T | null {
  try {
    const raw = store.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export const sortLetters = (s: string) => [...s].sort().join('')

export function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
}

export function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export const rateTone = (rate: number): 'good' | 'warn' | 'bad' => (rate >= 80 ? 'good' : rate >= 60 ? 'warn' : 'bad')
