import { registerMock } from './registry'
import type { PlanDayDetail, PlanToday, ScheduleItem, StatsOverview, UserPrefs, WeakSpot } from '@/api/types'

const pad = (n: number) => String(n).padStart(2, '0')
const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const now = new Date()
const todayStr = fmt(now)
const daysAgo = (n: number) => new Date(now.getTime() - n * 86400000)

const prefs: UserPrefs = {
  daily_goal: 30,
  exam_date: fmt(new Date(now.getTime() + 96 * 86400000)),
  weak_min_samples: 10,
  weak_max_rate: 0.6,
}
const checked = new Set<string>([1, 2, 3, 4, 6, 7, 8].map((n) => fmt(daysAgo(n))))
let doneToday = 12

const streak = () => {
  let n = 0
  const d = new Date(now)
  if (!checked.has(fmt(d))) d.setDate(d.getDate() - 1)
  while (checked.has(fmt(d))) { n++; d.setDate(d.getDate() - 1) }
  return n
}
const daysLeft = () => prefs.exam_date
  ? Math.max(0, Math.ceil((new Date(prefs.exam_date).getTime() - now.getTime()) / 86400000))
  : null

registerMock('GET', '/today', () => ({
  streak: streak(), checked_in: checked.has(todayStr), daily_goal: prefs.daily_goal, done_today: doneToday,
  exam_days_left: daysLeft(), exam_date: prefs.exam_date,
  counts: { due: 18, wrong: 42, starred: 9, mastered: 136 },
}))
registerMock('POST', '/checkin', () => { checked.add(todayStr); return { streak: streak() } })
registerMock('GET', '/calendar', ({ query }) => {
  const m = String(query.month)
  return { days: [...checked].filter((d) => d.startsWith(m)).map((d) => Number(d.slice(8))), streak: streak() }
})
registerMock('GET', '/prefs', () => prefs)
registerMock('PUT', '/prefs', ({ body }) => Object.assign(prefs, body))

const TERMS = ['肺炎链球菌肺炎', '慢性阻塞性肺疾病', '支气管哮喘', '心力衰竭', '房颤', '急性心肌梗死', '消化性溃疡', '肝硬化', '肾病综合征', '缺铁性贫血']
const OPT_PARTS: [string, number, number][] = [
  ['01-呼吸系统疾病', 238, 620], ['02-循环系统疾病', 396, 860], ['03-消化系统疾病', 286, 540],
  ['04-泌尿系统疾病', 216, 380], ['05-血液系统疾病', 257, 450], ['06-内分泌与代谢疾病', 215, 320],
]
let planItems: { subject: string; part: string; cards: number; questions: number; done: boolean }[] | null = [
  { subject: '内科学', part: '01-呼吸系统疾病', cards: 238, questions: 620, done: false },
  { subject: '内科学', part: '02-循环系统疾病', cards: 396, questions: 860, done: false },
  { subject: '外科学', part: '01-休克与复苏', cards: 165, questions: 210, done: true },
]
let planDays = 7

registerMock('GET', '/plan/options', () => [
  { subject: '内科学', parts: OPT_PARTS.map(([part, cards, questions]) => ({ part, cards, questions })) },
  { subject: '外科学', parts: [
    { part: '01-休克与复苏', cards: 165, questions: 210 }, { part: '02-水、电解质与酸碱平衡', cards: 142, questions: 180 },
    { part: '03-麻醉', cards: 62, questions: 90 },
  ] },
  { subject: '生理学', parts: [
    { part: '01-绪论', cards: 50, questions: 120 }, { part: '05-呼吸', cards: 118, questions: 300 },
  ] },
])
registerMock('PUT', '/plan/config', ({ body }) => {
  const b = body as { total_days: number; items: { subject: string; part: string }[] }
  planDays = b.total_days
  planItems = b.items.map((i) => ({
    ...i, done: false,
    cards: OPT_PARTS.find(([p]) => p === i.part)?.[1] ?? 40,
    questions: OPT_PARTS.find(([p]) => p === i.part)?.[2] ?? 90,
  }))
})
registerMock('DELETE', '/plan/config', () => { planItems = null })
registerMock('POST', '/plan/preview', ({ body }) => {
  const b = body as { total_days: number; items: { subject: string; part: string }[] }
  const cards = b.items.reduce((n, i) => n + (OPT_PARTS.find(([p]) => p === i.part)?.[1] ?? 40), 0)
  const questions = b.items.reduce((n, i) => n + (OPT_PARTS.find(([p]) => p === i.part)?.[2] ?? 90), 0)
  return { cards, questions, pending_cards: cards, pending_questions: questions,
    daily_cards: Math.ceil(cards / b.total_days), daily_questions: Math.ceil(questions / b.total_days), duplicate_questions_skipped: 0 }
})

const planItemOut = (i: NonNullable<typeof planItems>[number], day: number | null, cd: number, qd: number) => ({
  key: `${i.subject}|${i.part}`, subject: i.subject, part: i.part, label: `${i.subject} · ${i.part}`,
  cards: i.cards, card_done: i.done ? i.cards : cd, questions: i.questions, question_done: i.done ? i.questions : qd,
  done: i.done, day,
})
registerMock('GET', '/plan', (): PlanToday => {
  if (!planItems?.length) return { configured: false } as PlanToday
  const remaining = planItems.filter((i) => !i.done)
  const daysLeft = Math.max(1, planDays - 2)
  const batch = Math.max(1, Math.ceil(remaining.length / daysLeft))
  let di = 0
  const items = planItems.map((i) => planItemOut(i, i.done ? null : (di++ / batch | 0) + 1, 120, 300))
  return {
    configured: true, start: fmt(daysAgo(2)), total_days: planDays, day_no: 3, days_left: daysLeft,
    remaining: remaining.length, finished: remaining.length === 0,
    today_questions: items.filter((i) => i.day === 1).reduce((n, i) => n + Math.max(0, i.questions - i.question_done), 0),
    today_cards: items.filter((i) => i.day === 1).reduce((n, i) => n + Math.max(0, i.cards - i.card_done), 0),
    pending_questions: items.reduce((n, i) => n + Math.max(0, i.questions - i.question_done), 0),
    pending_cards: items.reduce((n, i) => n + Math.max(0, i.cards - i.card_done), 0),
    scheduled_days: [...new Set(items.flatMap((i) => i.day === null ? [] : [i.day]))].sort((a, b) => a - b),
    today_items: items.filter((i) => i.day === 1), items,
    today_sections: items.filter((i) => i.day === 1).map((i) => ({ key: i.key, subject: i.subject, part: i.part,
      label: i.label, cards: Math.max(0, i.cards - i.card_done), questions: Math.max(0, i.questions - i.question_done) })),
    day_summaries: [...new Set(items.flatMap((i) => i.day === null ? [] : [i.day]))].sort((a, b) => a - b).map((no) => ({
      no, date: fmt(daysAgo(1 - no)), overdue_cards: 0, overdue_questions: 0,
      cards: items.filter((i) => i.day === no).reduce((n, i) => n + Math.max(0, i.cards - i.card_done), 0),
      questions: items.filter((i) => i.day === no).reduce((n, i) => n + Math.max(0, i.questions - i.question_done), 0),
    })),
  }
})
registerMock('GET', '/plan/days/{n}', ({ params }): PlanDayDetail => {
  const n = Number(params.n)
  const cards = Array.from({ length: 8 }, (_, i) => n * 100 + i + 1)
  const chs = ['呼吸系统疾病', '循环系统疾病']
  return {
    no: n, title: '01-呼吸系统疾病',
    cards: cards.map((id, i) => ({ id, term: TERMS[(i + n) % TERMS.length], part: chs[i % 2] })),
    question_groups: chs.map((chapter, gi) => ({ subject_dir: '内科学', chapter, ids: Array.from({ length: 12 }, (_, i) => n * 1000 + gi * 20 + i) })),
  }
})
registerMock('POST', '/plan/restart', () => undefined)

const items: ScheduleItem[] = [
  { id: 1, item_type: 'question', item_id: 3011, reason: 'due', title: '慢性阻塞性肺疾病的肺功能特征性改变是', done: true },
  { id: 2, item_type: 'card', item_id: 201, reason: 'due', title: '心力衰竭的诱因与基本病因', done: true },
  { id: 3, item_type: 'question', item_id: 3025, reason: 'weak', title: '股骨颈骨折的分型及并发症', done: false },
  { id: 4, item_type: 'question', item_id: 3042, reason: 'due', title: '肺血栓栓塞症最可靠的确诊检查', done: false },
  { id: 5, item_type: 'card', item_id: 305, reason: 'weak', title: '肾病综合征的并发症', done: false },
  { id: 6, item_type: 'question', item_id: 3057, reason: 'weak', title: '肝性脑病的诱因与处理', done: false },
]
registerMock('GET', '/schedule/today', () => ({
  day: todayStr, goal: items.length, items, done_count: items.filter((i) => i.done).length,
}))
registerMock('POST', '/schedule/items/{id}/done', ({ params }) => {
  const it = items.find((i) => i.id === Number(params.id))
  if (it && !it.done) { it.done = true; doneToday++ }
})

const SPOTS: WeakSpot[] = [
  { system: '外科学', chapter: '骨科·骨折概论', total: 18, correct: 6, rate: 0.33, last_attempt_at: fmt(daysAgo(1)) + 'T21:10:00' },
  { system: '生理学', chapter: '血液循环', total: 25, correct: 11, rate: 0.44, last_attempt_at: fmt(daysAgo(2)) + 'T19:30:00' },
  { system: '病理学', chapter: '肿瘤', total: 12, correct: 6, rate: 0.5, last_attempt_at: fmt(daysAgo(4)) + 'T08:45:00' },
  { system: '内科学', chapter: '循环系统疾病', total: 40, correct: 22, rate: 0.55, last_attempt_at: fmt(now) + 'T09:05:00' },
  { system: '内科学', chapter: '呼吸系统疾病', total: 31, correct: 18, rate: 0.58, last_attempt_at: fmt(daysAgo(3)) + 'T22:00:00' },
]
registerMock('GET', '/stats/weakspots', () => [...SPOTS].sort((a, b) => a.rate - b.rate))

registerMock('GET', '/stats/overview', (): StatsOverview => ({
  total_questions: 4863, total_cards: 1520, total_chapters: 168, attempted: 612, accuracy: 0.68,
  by_system: [
    { system: '内科学', total: 210, correct: 150, rate: 0.71 }, { system: '外科学', total: 140, correct: 82, rate: 0.59 },
    { system: '生理学', total: 120, correct: 78, rate: 0.65 }, { system: '生物化学', total: 80, correct: 57, rate: 0.71 },
    { system: '病理学', total: 62, correct: 31, rate: 0.5 },
  ],
  daily: Array.from({ length: 30 }, (_, i) => {
    const count = i % 7 === 5 ? 0 : 8 + ((i * 13) % 37)
    return { day: fmt(daysAgo(29 - i)), count, correct: Math.round(count * (0.55 + ((i * 7) % 20) / 100)) }
  }),
}))
