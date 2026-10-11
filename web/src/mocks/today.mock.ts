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

const PLAN_TITLES = [
  '内科 · 呼吸 + 中毒', '内科 · 循环', '内科 · 消化 + 其他', '内科 · 泌尿 + 血液',
  '内科 · 内分泌/风湿 + 外科 · 颈部/乳房', '外科 · 休克/水电酸碱/麻醉/总论', '外科 · 围术期/感染/输血',
  '外科 · 创伤烧伤/肿瘤/胸外/疝/腹损/血管/泌外', '外科 · 消化普外（胃/阑尾/肠/肝胆胰）', '外科 · 骨科全部 + 收尾',
]
const CHAPTERS: string[][] = [
  ['呼吸系统疾病', '中毒与理化因素'], ['循环系统疾病'], ['消化系统疾病', '其他与综合'], ['泌尿系统疾病', '血液系统疾病'],
  ['内分泌与代谢疾病', '风湿免疫疾病', '颈部疾病'], ['休克与复苏', '麻醉'], ['围术期处理', '外科感染', '输血'],
  ['创伤与烧伤', '肿瘤与移植', '胸部疾病', '腹外疝'], ['胃十二指肠疾病', '阑尾炎', '肝疾病与门静脉高压', '胆道疾病'],
  ['骨折概论', '上肢骨折脱位', '下肢骨折与骨盆', '脊柱脊髓'],
]
const TERMS = ['肺炎链球菌肺炎', '慢性阻塞性肺疾病', '支气管哮喘', '心力衰竭', '房颤', '急性心肌梗死', '消化性溃疡', '肝硬化', '肾病综合征', '缺铁性贫血']
let planStart = 3
const planNo = () => Math.min(PLAN_TITLES.length + 1, planStart <= 0 ? 1 : planStart)

function dayIds(n: number) {
  const cards = Array.from({ length: 12 }, (_, i) => n * 100 + i + 1)
  const qs = Array.from({ length: 24 }, (_, i) => n * 1000 + i + 1)
  return { cards, qs }
}
registerMock('GET', '/plan', (): PlanToday => {
  const no = planNo()
  const finished = no > PLAN_TITLES.length
  const { cards, qs } = dayIds(Math.min(no, PLAN_TITLES.length))
  return {
    start: fmt(daysAgo(no - 1)), total_days: PLAN_TITLES.length, today_no: no, finished,
    title: finished ? '计划已完成' : PLAN_TITLES[no - 1],
    card_ids: finished ? [] : cards, question_ids: finished ? [] : qs,
    card_done: finished ? 0 : 7, question_done: finished ? 0 : 9,
    overview: PLAN_TITLES.map((title, i) => ({ no: i + 1, title, card_count: 12 + (i % 4) * 3 })),
  }
})
registerMock('GET', '/plan/days/{n}', ({ params }): PlanDayDetail => {
  const n = Number(params.n)
  const { cards, qs } = dayIds(n)
  const chs = CHAPTERS[n - 1] ?? []
  const per = Math.ceil(qs.length / Math.max(chs.length, 1))
  return {
    no: n, title: PLAN_TITLES[n - 1] ?? '',
    cards: cards.slice(0, 8).map((id, i) => ({ id, term: TERMS[(i + n) % TERMS.length], part: chs[i % Math.max(chs.length, 1)] ?? '' })),
    question_groups: chs.map((chapter, i) => ({ chapter, ids: qs.slice(i * per, (i + 1) * per) })),
  }
})
registerMock('POST', '/plan/restart', () => { planStart = 1 })

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
