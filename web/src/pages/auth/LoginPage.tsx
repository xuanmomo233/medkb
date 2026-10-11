import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useAuth } from '@/app/auth'
import { Button, Field, Input, Segmented, useToast } from '@/ui'
import s from './auth.module.css'

type Mode = 'login' | 'register'
interface Errors { username?: string; password?: string; invite?: string }

const NAME_RE = /^[\u4e00-\u9fa5A-Za-z0-9_-]{2,24}$/

function validate(mode: Mode, username: string, password: string, invite: string): Errors {
  const e: Errors = {}
  if (!NAME_RE.test(username)) e.username = '用户名为 2-24 位中英文、数字、下划线或短横线'
  if (password.length < 6) e.password = '密码至少 6 位'
  if (mode === 'register' && !invite.trim()) e.invite = '请输入邀请码'
  return e
}

export default function LoginPage() {
  const { user, signIn } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const toast = useToast()
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [invite, setInvite] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')

  if (user) return <Navigate to="/" replace />
  const from = (loc.state as { from?: string } | null)?.from || '/'

  const submit = async (ev: FormEvent) => {
    ev.preventDefault()
    const name = username.trim()
    const errs = validate(mode, name, password, invite)
    setErrors(errs)
    setFormError('')
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      const r = mode === 'login'
        ? await api.login({ username: name, password })
        : await api.register({ username: name, password, invite_code: invite.trim() })
      signIn(r)
      toast(mode === 'login' ? '欢迎回来' : '注册成功')
      nav(from, { replace: true })
    } catch (err) {
      setFormError(err instanceof Error ? err.message : '操作失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={s.page}>
      <form className={s.card} onSubmit={submit} noValidate>
        <div className={s.logo} aria-hidden="true">⚕</div>
        <h1 className={s.title}>医学知识库</h1>
        <p className={s.slogan}>刷题、背卡、AI 陪学，西综备考一站搞定</p>
        <Segmented<Mode> value={mode} onChange={(m) => { setMode(m); setErrors({}); setFormError('') }}
          options={[{ value: 'login', label: '登录' }, { value: 'register', label: '注册' }]} />
        <div className={s.fields}>
          <Field label="用户名">
            <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
              aria-invalid={!!errors.username} placeholder="2-24 位，支持中英文" />
            {errors.username && <span className={s.error} role="alert">{errors.username}</span>}
          </Field>
          <Field label="密码">
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              aria-invalid={!!errors.password} placeholder="至少 6 位" />
            {errors.password && <span className={s.error} role="alert">{errors.password}</span>}
          </Field>
          {mode === 'register' && (
            <Field label="邀请码">
              <Input value={invite} onChange={(e) => setInvite(e.target.value)} autoComplete="off"
                aria-invalid={!!errors.invite} placeholder="向管理员获取" />
              {errors.invite && <span className={s.error} role="alert">{errors.invite}</span>}
            </Field>
          )}
        </div>
        {formError && <div className={s.formError} role="alert">{formError}</div>}
        <Button type="submit" variant="primary" size="lg" block disabled={busy}>
          {busy ? '提交中…' : mode === 'login' ? '登录' : '注册并登录'}
        </Button>
      </form>
    </div>
  )
}
