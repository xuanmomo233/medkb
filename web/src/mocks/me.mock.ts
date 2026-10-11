import { registerMock } from './registry'

registerMock('GET', '/version', () => ({ build: 128, note: '新增薄弱点阈值设置；AI 陪学支持图片与文件；修复若干排版问题。' }))


const invites: { code: string; created_by: number; used_by: number | null; used_at: string | null; created_at: string | null }[] = []
registerMock('GET', '/admin/invites', () => invites)
registerMock('POST', '/admin/invites', ({ body }) => {
  const n = Math.min(50, Math.max(1, Number((body as { count?: number })?.count ?? 1)))
  const out = Array.from({ length: n }, () => ({
    code: Math.random().toString(36).slice(2, 14),
    created_by: 1, used_by: null, used_at: null, created_at: new Date().toISOString(),
  }))
  invites.unshift(...out)
  return out
})
registerMock('DELETE', '/admin/invites/{code}', ({ params }) => {
  const i = invites.findIndex((c) => c.code === params.code)
  if (i >= 0) invites.splice(i, 1)
})
