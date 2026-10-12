import { registerMock } from './registry'

registerMock('GET', '/version', () => ({ build: 128, note: '新增薄弱点阈值设置；AI 陪学支持图片与文件；修复若干排版问题。' }))


const users = [
  { id: 1, username: 'mo', is_admin: true, created_at: '2026-03-01T00:00:00Z', last_login_at: '2026-03-25T00:00:00Z', invite_code: null },
  { id: 2, username: 'demo', is_admin: false, created_at: '2026-03-10T00:00:00Z', last_login_at: '2026-03-24T00:00:00Z', invite_code: 'abc123xyz' },
]
const invites: { code: string; created_by: number; used_by: number | null; used_by_username: string | null; used_at: string | null; created_at: string | null }[] = [
  { code: 'abc123xyz', created_by: 1, used_by: 2, used_by_username: 'demo', used_at: '2026-03-10T00:00:00Z', created_at: '2026-03-09T00:00:00Z' },
]
registerMock('GET', '/admin/users', ({ query }) => {
  const nameQ = String(query.q ?? '').toLowerCase()
  const invQ = String(query.invite ?? '')
  return users.filter((u) => (!nameQ || u.username.toLowerCase().includes(nameQ))
    && (!invQ || u.invite_code === invQ))
})
registerMock('DELETE', '/admin/users/{id}', ({ params, body }) => {
  const u = users.find((x) => x.id === Number(params.id))
  if (!u) throw Object.assign(new Error('用户不存在'), { status: 404 })
  if ((body as { password?: string })?.password !== '123456')
    throw Object.assign(new Error('管理员密码错误'), { status: 403 })
  users.splice(users.indexOf(u), 1)
})
registerMock('GET', '/admin/invites', () => invites)
registerMock('POST', '/admin/invites', ({ body }) => {
  const n = Math.min(50, Math.max(1, Number((body as { count?: number })?.count ?? 1)))
  const out = Array.from({ length: n }, () => ({
    code: Math.random().toString(36).slice(2, 14),
    created_by: 1, used_by: null, used_by_username: null, used_at: null, created_at: new Date().toISOString(),
  }))
  invites.unshift(...out)
  return out
})
registerMock('DELETE', '/admin/invites/{code}', ({ params }) => {
  const i = invites.findIndex((c) => c.code === params.code)
  if (i >= 0) invites.splice(i, 1)
})

registerMock('PUT', '/auth/password', ({ body }) => {
  const b = body as { old_password?: string; new_password?: string }
  if (!b?.old_password) throw Object.assign(new Error('原密码错误'), { status: 403 })
  if ((b.new_password ?? '').length < 8) throw Object.assign(new Error('新密码至少 8 位'), { status: 400 })
  return undefined
})

let siteExamDate = '2026-12-19'
registerMock('GET', '/admin/site', () => ({ exam_date: siteExamDate }))
registerMock('PUT', '/admin/site', ({ body }) => {
  const b = body as { exam_date?: string | null }
  siteExamDate = b?.exam_date || '2026-12-19'
  return { exam_date: siteExamDate }
})
