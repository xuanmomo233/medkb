import type { CardQuery } from '@/api/types'

export function parseQuery(p: URLSearchParams): CardQuery {
  const q: CardQuery = {}
  const subject = p.get('subject')
  const part = p.get('part')
  const ids = p.get('ids')
  const day = Number(p.get('plan_day'))
  if (subject) q.subject = subject
  if (part) q.part = part
  if (ids) q.ids = ids.split(',').map(Number).filter((n) => Number.isFinite(n) && n > 0)
  if (day > 0) q.plan_day = day
  if (p.get('starred') === '1') q.starred = true
  if (p.get('due') === '1') q.due = true
  return q
}

export function queryTitle(q: CardQuery): string {
  if (q.due) return '到期复习'
  if (q.starred) return '收藏卡片'
  if (q.plan_day) return `今日计划 · 第 ${q.plan_day} 天`
  if (q.part) return `${q.subject ?? ''} · ${q.part}`
  if (q.ids) return '指定卡片'
  return '背卡'
}

export type Rating = 'rate_again' | 'rate_hard' | 'rate_good'
