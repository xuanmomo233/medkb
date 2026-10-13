import { registerMock } from './registry'
import type { Note, PublicNote, TargetType } from '@/api/types'
import { mockQuestionAdmin, updateMockQuestion } from './quiz.mock'

interface Rec extends Note { user: string; likes: number; liked: boolean }
let nextId = 100
const day = (n: number) => new Date(Date.now() - n * 864e5).toISOString()
const store: Rec[] = [
  { id: 1, target_type: 'question', target_id: 1, body: '心衰首选 β 阻滞剂要从小剂量起始。', is_public: false, created_at: day(2), stem_preview: '下列药物中，可改善慢性收缩性心力衰竭患者预后的是？', user: 'me', likes: 0, liked: false },
  { id: 2, target_type: 'question', target_id: 1, body: '记忆口诀：ACEI + β + 醛固酮拮抗剂，“金三角”。', is_public: true, created_at: day(1), stem_preview: '下列药物中，可改善慢性收缩性心力衰竭患者预后的是？', user: 'me', likes: 2, liked: false },
  { id: 3, target_type: 'question', target_id: 1, body: '地高辛不降低死亡率，只减少住院。', is_public: true, created_at: day(3), user: '学霸小王', likes: 5, liked: false },
  { id: 4, target_type: 'card', target_id: 3, body: '肺动脉高压的分级标准要记。', is_public: false, created_at: day(5), stem_preview: '肺动脉高压', user: 'me', likes: 0, liked: false },
]
const strip = ({ id, target_type, target_id, body, is_public, created_at, stem_preview }: Rec): Note =>
  ({ id, target_type, target_id, body, is_public, created_at, stem_preview })
const match = (q: Record<string, unknown>) => (n: Rec) => n.target_type === (q.target_type as TargetType) && n.target_id === Number(q.target_id)
const byTime = (a: Rec, b: Rec) => b.created_at.localeCompare(a.created_at)

registerMock('GET', '/notes', ({ query }) => store.filter(match(query)).filter((n) => n.user === 'me').sort(byTime).map(strip))
registerMock('GET', '/notes/mine', () => store.filter((n) => n.user === 'me').sort(byTime).map(strip))
registerMock('POST', '/notes', ({ body }) => {
  const b = body as Pick<Note, 'target_type' | 'target_id' | 'body' | 'is_public'>
  store.push({ ...b, id: nextId++, created_at: new Date().toISOString(), user: 'me', likes: 0, liked: false })
})
registerMock('GET', '/notes/public', ({ query }): PublicNote[] =>
  store.filter(match(query)).filter((n) => n.is_public)
    .map((n) => ({ id: n.id, body: n.body, created_at: n.created_at, username: n.user === 'me' ? '我' : n.user, likes: n.likes, liked: n.liked, mine: n.user === 'me' })))
registerMock('POST', '/notes/{id}/like', ({ params }) => {
  const n = store.find((x) => x.id === Number(params.id))
  if (!n) throw new Error('笔记不存在')
  n.liked = !n.liked
  n.likes += n.liked ? 1 : -1
  return { likes: n.likes, liked: n.liked }
})
registerMock('DELETE', '/notes/{id}', ({ params }) => {
  const i = store.findIndex((x) => x.id === Number(params.id))
  if (i >= 0) store.splice(i, 1)
})

const admin = new Map<number, { id: number; stem: string; system: string; analysis: string; tags: string[] }>()
registerMock('GET', '/admin/questions/{id}', ({ params }) => {
  const id = Number(params.id)
  if (!admin.has(id)) admin.set(id, { id, stem: mockQuestionAdmin(id)?.stem ?? '', system: mockQuestionAdmin(id)?.system ?? '循环系统', analysis: '## 解析\n\nβ 受体阻滞剂可改善 **HFrEF** 预后。\n\n- 从小剂量开始\n- 逐渐加量', tags: ['心衰', '药物治疗'] })
  return admin.get(id)
})
registerMock('PUT', '/admin/questions/{id}', ({ params, body }) => {
  const id = Number(params.id)
  const cur = admin.get(id)
  if (!cur) throw new Error('题目不存在')
  const p = body as Partial<typeof cur>
  Object.assign(cur, p)
  updateMockQuestion(id, p)
  return { changed: Object.keys(p).length }
})
