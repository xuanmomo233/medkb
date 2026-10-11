import { registerMock } from './registry'
import type { AuthResult, User } from '@/api/types'

let current: User = { id: 1, username: 'demo', is_admin: false }

function make(username: string): AuthResult {
  current = { id: username === 'admin' ? 1 : 2, username, is_admin: username === 'admin' }
  return { token: `mock-${username}`, user: current }
}

function check(body: unknown) {
  const b = body as { username?: string; password?: string }
  if (!b.username || !b.password || b.password.length < 6) throw new Error('用户名或密码错误')
  return b.username
}

registerMock('POST', '/auth/login', ({ body }) => make(check(body)))
registerMock('POST', '/auth/register', ({ body }) => {
  const code = (body as { invite_code?: string }).invite_code
  if (!code) throw new Error('邀请码无效')
  return make(check(body))
})
registerMock('GET', '/auth/me', () => current)
registerMock('POST', '/auth/logout', () => undefined)
