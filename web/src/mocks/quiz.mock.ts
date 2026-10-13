import { registerMock } from '@/mocks/registry'
import type {
  AttemptResult, ExamRecord, ExamReport, FacetLevel, FacetProgress, PoolItem, PoolPage, ProgressState,
  Question, QuestionFull, QuestionStat, QuizFilter, SubmitItem, WrongBookGroup,
} from '@/api/types'
import { RAW } from './quiz-data/bank'

const LEVELS: FacetLevel[] = ['bank_group', 'bank', 'subject_dir', 'system', 'chapter', 'qtype']
const LETTERS = 'ABCDEFGH'

interface Rec extends Question { bank_group: string; bank: string; subject_dir: string; plain: string }
interface Attempt { picked: string; correct: boolean; count: number; wrong: number; lastWrongAt: string | null }
interface Mark { state: ProgressState; starred: boolean }

const BANKS = ['2022年真题', '2023年真题', '2024年模拟题']

const bank: Rec[] = RAW.map(([system, subject, chapter, stem, options, answer, analysis, parent], i) => {
  const bankName = BANKS[i % 3]
  return {
    id: 1001 + i, qid: `${bankName.slice(0, 4)}-${String(i + 1).padStart(3, '0')}`,
    chapter, system, qtype: parent ? '病例串' : answer.length > 1 ? 'X型题' : 'A型题',
    stem_html: stem, parent_html: parent ?? '', options_html: options, answer, analysis_html: analysis,
    analysis_empty: !analysis, tags: i % 4 === 0 ? ['高频'] : i % 7 === 0 ? ['易错'] : [],
    state: '', starred: false, done: false, last_picked: '', last_correct: null,
    bank_group: i % 3 === 2 ? '模拟题库' : '西综真题', bank: bankName, subject_dir: subject,
    plain: stem.replace(/<[^>]+>/g, ''),
  }
})

const attempts = new Map<number, Attempt>()
const marks = new Map<number, Mark>()
const aiDone = new Map<number, string>()
const exams: ExamRecord[] = [
  { id: 1, created_at: new Date(Date.now() - 3 * 86400000).toISOString(), title: '呼吸系统测试', total: 20, correct: 15, rate: 75 },
  { id: 2, created_at: new Date(Date.now() - 86400000).toISOString(), title: '全真模考', total: 60, correct: 31, rate: 51.7 },
]

const find = (id: number) => bank.find((q) => q.id === id)
const mark = (id: number): Mark => marks.get(id) ?? { state: '', starred: false }
export function mockQuestionAdmin(id: number) {
  const q = find(id)
  return q ? { stem: q.plain, system: q.system } : null
}
export function updateMockQuestion(id: number, patch: { stem?: string; system?: string; analysis?: string; tags?: string[] }) {
  const q = find(id)
  if (!q) return
  if (patch.stem !== undefined) { q.plain = patch.stem; q.stem_html = `<p>${patch.stem}</p>` }
  if (patch.system !== undefined) q.system = patch.system
  if (patch.analysis !== undefined) { q.analysis_html = `<p>${patch.analysis}</p>`; q.analysis_empty = !patch.analysis }
  if (patch.tags !== undefined) q.tags = patch.tags
}
const num = (v: unknown) => (v === undefined || v === '' ? undefined : Number(v))
const flag = (v: unknown) => v === true || v === '1' || v === 'true'
const idList = (v: unknown): number[] => (Array.isArray(v) ? v : String(v ?? '').split(',')).map(Number).filter(Boolean)
const letters = (idx: number[]) => idx.map((i) => LETTERS[i]).sort().join('')
const sortLetters = (s: string) => [...s].sort().join('')

function matches(q: Rec, f: QuizFilter, upTo = LEVELS.length) {
  return LEVELS.slice(0, upTo).every((k) => {
    const v = f[k]
    return !v || (k === 'chapter' ? q.chapter : k === 'qtype' ? q.qtype : q[k]) === v
  })
}

function view(q: Rec, lite: boolean): Question {
  const a = attempts.get(q.id)
  const m = mark(q.id)
  const { bank_group: _g, bank: _b, subject_dir: _s, plain: _p, ...rest } = q
  void _g; void _b; void _s; void _p
  return {
    ...rest, analysis_html: lite ? '' : aiDone.get(q.id) ?? q.analysis_html,
    analysis_empty: q.analysis_empty && !aiDone.has(q.id),
    state: m.state, starred: m.starred, done: !!a, last_picked: a?.picked ?? '', last_correct: a ? a.correct : null,
  }
}

function stat(q: Rec): QuestionStat {
  const total = 40 + (q.id * 7) % 90
  const correctN = Math.round(total * (0.35 + ((q.id * 13) % 50) / 100))
  const dist: Record<string, number> = {}
  const n = q.options_html.length
  const rest = total - correctN
  q.options_html.forEach((_, i) => {
    const L = LETTERS[i]
    dist[L] = q.answer.includes(L) ? Math.round(correctN / q.answer.length) : Math.round(rest / Math.max(1, n - q.answer.length))
  })
  const mine = attempts.get(q.id)
  if (mine) {
    for (const c of mine.picked) dist[c] = (dist[c] ?? 0) + 1
    return { total: total + 1, correct: correctN + (mine.correct ? 1 : 0), dist }
  }
  return { total, correct: correctN, dist }
}

function shuffle<T>(a: T[]): T[] {
  const r = [...a]
  for (let i = r.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [r[i], r[j]] = [r[j], r[i]] }
  return r
}

registerMock('GET', '/quiz/facets', ({ query }) => {
  const f = query as QuizFilter
  const out = {} as FacetProgress
  LEVELS.forEach((lv, i) => {
    const o: Record<string, [number, number]> = {}
    for (const q of bank.filter((x) => matches(x, f, i))) {
      const key = lv === 'chapter' ? q.chapter : lv === 'qtype' ? q.qtype : q[lv]
      const cur = o[key] ?? [0, 0]
      o[key] = [cur[0] + 1, cur[1] + (attempts.has(q.id) ? 1 : 0)]
    }
    out[lv] = o
  })
  return out
})

registerMock('GET', '/quiz/questions', ({ query }) => {
  const f = query as QuizFilter
  let list = bank.filter((q) => matches(q, f))
  const ids = idList(query.ids)
  if (ids.length) list = ids.map(find).filter((q): q is Rec => !!q)
  if (flag(query.starred)) list = list.filter((q) => mark(q.id).starred)
  if (flag(query.wrong)) list = list.filter((q) => mark(q.id).state === 'again')
  if (flag(query.random)) list = list.filter((q) => mark(q.id).state !== 'mastered')
  if (flag(query.random) || flag(query.shuffle)) list = shuffle(list)
  const limit = num(query.limit)
  if (limit) list = list.slice(0, limit)
  return list.map((q) => view(q, flag(query.lite)))
})

registerMock('GET', '/quiz/questions/{id}', ({ params }): QuestionFull => {
  const q = find(Number(params.id))
  if (!q) throw new Error('题目不存在')
  const v = view(q, false)
  const related = q.analysis_empty
    ? [{ id: 9001, term: q.chapter, term_html: q.chapter, hint: '本章核心考点', body_html: `<p>${q.chapter}相关要点：结合教材章节复习，重点掌握定义、机制与典型临床表现。</p>` }]
    : []
  return {
    id: q.id, system: q.system, stem_html: q.stem_html, answer: q.answer, analysis_html: v.analysis_html, analysis_empty: v.analysis_empty,
    related_cards: related, stat: stat(q), tags: q.tags, state: v.state, starred: v.starred,
  }
})

registerMock('POST', '/quiz/questions/{id}/ai-analysis', ({ params }) => {
  const q = find(Number(params.id))
  if (!q) throw new Error('题目不存在')
  const html = `<p><strong>AI 解析：</strong>正确答案为 ${q.answer}。骨折愈合分为血肿炎症机化期、原始骨痂形成期和骨痂改造塑形期三个阶段，三个阶段均属于愈合过程，故选 D。</p>`
  aiDone.set(q.id, html)
  return { analysis_html: html }
})

registerMock('POST', '/quiz/attempts', ({ body }): AttemptResult => {
  const b = body as { question_id: number; picked: number[] }
  const q = find(b.question_id)
  if (!q) throw new Error('题目不存在')
  const picked = letters(b.picked)
  const correct = picked === sortLetters(q.answer)
  const old = attempts.get(q.id)
  attempts.set(q.id, {
    picked, correct, count: (old?.count ?? 0) + 1, wrong: (old?.wrong ?? 0) + (correct ? 0 : 1),
    lastWrongAt: correct ? old?.lastWrongAt ?? null : new Date().toISOString(),
  })
  if (!correct) marks.set(q.id, { ...mark(q.id), state: 'again' })
  return { correct, answer: q.answer, stat: stat(q) }
})

registerMock('POST', '/quiz/submit', ({ body }): ExamReport => {
  const b = body as { title: string; items: SubmitItem[] }
  const results: ExamReport['results'] = []
  const chap = new Map<string, { total: number; correct: number }>()
  const wrongIds: number[] = []
  let correct = 0
  for (const it of b.items) {
    const q = find(it.question_id)
    if (!q) continue
    if (!it.picked.length) { results.push({ question_id: q.id, judged: false, answer: q.answer }); continue }
    const ok = letters(it.picked) === sortLetters(q.answer)
    const old = attempts.get(q.id)
    attempts.set(q.id, {
      picked: letters(it.picked), correct: ok, count: (old?.count ?? 0) + 1, wrong: (old?.wrong ?? 0) + (ok ? 0 : 1),
      lastWrongAt: ok ? old?.lastWrongAt ?? null : new Date().toISOString(),
    })
    if (!ok) { wrongIds.push(q.id); marks.set(q.id, { ...mark(q.id), state: 'again' }) }
    else correct++
    const c = chap.get(q.chapter) ?? { total: 0, correct: 0 }
    chap.set(q.chapter, { total: c.total + 1, correct: c.correct + (ok ? 1 : 0) })
    results.push({ question_id: q.id, judged: true, correct: ok, answer: q.answer })
  }
  const total = b.items.length
  const rate = total ? correct / total : 0
  exams.unshift({ id: exams.length + 1, created_at: new Date().toISOString(), title: b.title, total, correct, rate: Math.round(rate * 1000) / 10 })
  return {
    total, correct, score_100: Math.round(rate * 1000) / 10, score_300: Math.round(rate * 300),
    wrong_ids: wrongIds, results,
    by_chapter: [...chap].map(([chapter, c]) => ({ chapter, total: c.total, correct: c.correct, rate: Math.round((c.correct / c.total) * 100) })),
  }
})

registerMock('GET', '/quiz/mock', ({ query }) => ({ ids: shuffle(bank).slice(0, Math.min(num(query.n) ?? 180, bank.length)).map((q) => q.id) }))

registerMock('GET', '/quiz/pool', ({ query }): PoolPage => {
  const base = bank.filter((q) => matches(q, query as QuizFilter))
  const count = (fn: (q: Rec) => boolean) => base.filter(fn).length
  const stats = {
    total: base.length, done: count((q) => attempts.has(q.id)), wrong: count((q) => mark(q.id).state === 'again'),
    starred: count((q) => mark(q.id).starred), plan: count((q) => mark(q.id).state === 'plan'),
    mastered: count((q) => mark(q.id).state === 'mastered'),
  }
  const flt = String(query.flt ?? '')
  const pick: Record<string, (q: Rec) => boolean> = {
    done: (q) => attempts.has(q.id), todo: (q) => !attempts.has(q.id), wrong: (q) => mark(q.id).state === 'again',
    starred: (q) => mark(q.id).starred, plan: (q) => mark(q.id).state === 'plan', mastered: (q) => mark(q.id).state === 'mastered',
  }
  const list = flt && pick[flt] ? base.filter(pick[flt]) : base
  const offset = num(query.offset) ?? 0
  const size = num(query.size) ?? 50
  const items: PoolItem[] = list.slice(offset, offset + size).map((q) => {
    const a = attempts.get(q.id)
    const m = mark(q.id)
    return {
      id: q.id, qid: q.qid, stem: q.plain, answer: q.answer, source: q.bank, tags: q.tags, state: m.state, starred: m.starred,
      in_plan: m.state === 'plan', done: !!a, attempts: a?.count ?? 0, wrong_count: a?.wrong ?? 0, last_wrong_at: a?.lastWrongAt ?? null,
    }
  })
  return { stats, items }
})

registerMock('GET', '/quiz/wrongbook', (): WrongBookGroup[] => {
  const g = new Map<string, WrongBookGroup>()
  for (const q of bank) {
    if (mark(q.id).state !== 'again') continue
    const a = attempts.get(q.id)
    const cur = g.get(q.chapter) ?? { chapter: q.chapter, count: 0, wrong_total: 0, last_wrong_at: null }
    cur.count++
    cur.wrong_total += a?.wrong ?? 1
    if (a?.lastWrongAt && (!cur.last_wrong_at || a.lastWrongAt > cur.last_wrong_at)) cur.last_wrong_at = a.lastWrongAt
    g.set(q.chapter, cur)
  }
  return [...g.values()].sort((x, y) => y.count - x.count)
})

registerMock('GET', '/quiz/exams', () => exams)

registerMock('POST', '/progress/mark', ({ body }) => {
  const b = body as { target_type: string; target_id: number; action: string }
  if (b.target_type !== 'question') return
  const m = mark(b.target_id)
  const next: Record<string, Partial<Mark>> = {
    star: { starred: true }, unstar: { starred: false }, wrong: { state: 'again' }, unwrong: { state: '' },
    master: { state: 'mastered' }, unmaster: { state: '' }, plan: { state: 'plan' }, unplan: { state: '' },
  }
  marks.set(b.target_id, { ...m, ...next[b.action] })
})
