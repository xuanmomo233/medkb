import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { AdminUser } from '@/api/types'
import { useAuth } from '@/app/auth'
import { Button, Card, ErrorState, Field, Input, Modal, PageHeader, Spinner, useToast } from '@/ui'
import s from './me.module.css'

const fmt = (iso: string | null) => iso ? iso.slice(0, 10) : '—'

function SiteCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['site'], queryFn: api.adminSite })
  const [d, setD] = useState('')
  useEffect(() => { if (q.data) setD(q.data.exam_date) }, [q.data])
  const save = useMutation({
    mutationFn: () => api.adminSaveSite({ exam_date: d || null }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['site'] }); qc.invalidateQueries({ queryKey: ['today'] }); toast(`考研日期已更新为 ${r.exam_date}`) },
    onError: (e: Error) => toast(e.message, true),
  })
  return (
    <Card title="站点设置">
      <div className={s.group}>
        <p className={s.sectionHint}>考研日期全体用户共用，清空恢复默认 2026-12-19</p>
        <Field label="考研日期">
          <Input type="date" value={d} onChange={(e) => setD(e.target.value)} />
        </Field>
        <div className={s.saveBar}>
          <Button variant="primary" disabled={save.isPending || q.isLoading} onClick={() => save.mutate()}>
            {save.isPending ? '保存中…' : '保存'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

function UsersCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const { user } = useAuth()
  const [nameQ, setNameQ] = useState('')
  const [inviteQ, setInviteQ] = useState('')
  const [flt, setFlt] = useState<{ q?: string; invite?: string }>({})
  const [target, setTarget] = useState<AdminUser | null>(null)
  const [step, setStep] = useState<'confirm' | 'password'>('confirm')
  const [pw, setPw] = useState('')
  const q = useQuery({ queryKey: ['adminUsers', flt], queryFn: () => api.adminUsers(flt) })
  const del = useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) => api.adminDeleteUser(id, password),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminUsers'] }); qc.invalidateQueries({ queryKey: ['invites'] })
      setTarget(null); setPw(''); toast('账号已删除')
    },
    onError: (e: Error) => toast(e.message, true),
    onSettled: () => setStep('confirm'),
  })
  const search = (f: { q?: string; invite?: string }) => setFlt({ q: f.q || undefined, invite: f.invite || undefined })
  return (
    <Card title="账户管理">
      <div className={s.group}>
        <p className={s.sectionHint}>查看全部注册账户；可按用户名搜索，或输入邀请码反查绑定它的账号。</p>
        <div className={s.userSearch}>
          <Input placeholder="按用户名搜索" value={nameQ}
            onChange={(e) => setNameQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search({ q: nameQ })} />
          <Button onClick={() => search({ q: nameQ })}>搜用户</Button>
        </div>
        <div className={s.userSearch}>
          <Input placeholder="按邀请码反查账号" value={inviteQ}
            onChange={(e) => setInviteQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search({ invite: inviteQ })} />
          <Button onClick={() => search({ invite: inviteQ })}>搜邀请码</Button>
          {(flt.q || flt.invite) && <Button variant="ghost" onClick={() => { setNameQ(''); setInviteQ(''); setFlt({}) }}>清除筛选</Button>}
        </div>
        {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
          <div className={s.userList}>
            {(q.data ?? []).map((u) => (
              <div key={u.id} className={s.userRow}>
                <span className={s.userMain}>
                  #{u.id} {u.username}
                  {u.is_admin && <span className={s.userCode}>管理员</span>}
                </span>
                <span className={s.userMeta}>
                  {u.invite_code ? <>邀请码 <code className={s.userCode}>{u.invite_code}</code></> : '无邀请码'}
                  {' · '}注册 {fmt(u.created_at)}{' · '}最近登录 {fmt(u.last_login_at)}
                </span>
                {!u.is_admin && u.id !== user?.id && (
                  <Button variant="danger" size="sm" onClick={() => { setTarget(u); setStep('confirm'); setPw('') }}>删除</Button>
                )}
              </div>
            ))}
            {q.data && q.data.length === 0 && <div className={s.desc}>没有匹配的账户。</div>}
          </div>
        )}
      </div>
      {target && step === 'confirm' && (
        <Modal title="删除账号" onClose={() => setTarget(null)}>
          <div className={s.group}>
            <div className={s.delWarn}>
              将永久删除账号 <strong>{target.username}</strong>（#{target.id}）及其全部学习数据，此操作不可恢复。确定要继续吗？
            </div>
            <div className={s.saveBar}>
              <Button variant="ghost" onClick={() => setTarget(null)}>取消</Button>
              <Button variant="danger" onClick={() => setStep('password')}>继续删除</Button>
            </div>
          </div>
        </Modal>
      )}
      {target && step === 'password' && (
        <Modal title="管理员验证" onClose={() => setTarget(null)}>
          <div className={s.group}>
            <div className={s.delWarn}>
              即将删除 <strong>{target.username}</strong>（#{target.id}）。请输入当前管理员账号的密码确认。
            </div>
            <Field label="管理员密码">
              <Input type="password" autoComplete="current-password" autoFocus value={pw}
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && pw && del.mutate({ id: target.id, password: pw })} />
            </Field>
            <div className={s.saveBar}>
              <Button variant="ghost" onClick={() => setStep('confirm')}>上一步</Button>
              <Button variant="danger" disabled={!pw || del.isPending}
                onClick={() => del.mutate({ id: target.id, password: pw })}>
                {del.isPending ? '删除中…' : '确认删除'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  )
}

function InvitesCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['invites'], queryFn: api.adminInvites })
  const create = useMutation({
    mutationFn: (n: number) => api.adminNewInvite(n),
    onSuccess: (rows) => {
      qc.invalidateQueries({ queryKey: ['invites'] })
      navigator.clipboard?.writeText(rows[0].code).catch(() => {})
      toast(rows.length > 1 ? `已生成 ${rows.length} 个邀请码` : `已生成并复制：${rows[0].code}`)
    },
    onError: (e: Error) => toast(e.message, true),
  })
  const revoke = useMutation({
    mutationFn: (code: string) => api.adminRevokeInvite(code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['invites'] }); toast('已撤销') },
    onError: (e: Error) => toast(e.message, true),
  })
  return (
    <Card title="邀请码管理">
      <div className={s.group}>
        <p className={s.sectionHint}>邀请码一次性使用，注册即作废。生成后请复制发给新用户。</p>
        <div className={s.saveBar}>
          <Button variant="primary" onClick={() => create.mutate(1)} disabled={create.isPending}>生成 1 个</Button>
          <Button onClick={() => create.mutate(5)} disabled={create.isPending}>生成 5 个</Button>
        </div>
        {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
          <div className={s.inviteList}>
            {(q.data ?? []).map((c) => (
              <div key={c.code} className={s.inviteRow}>
                <code className={c.used_by ? s.inviteUsed : s.inviteCode}>{c.code}</code>
                <span className={s.inviteMeta}>
                  {c.used_by ? `已被 ${c.used_by_username ?? `#${c.used_by}`} 使用` : '未使用'}
                </span>
                {c.used_by == null && (
                  <>
                    <Button onClick={() => { navigator.clipboard?.writeText(c.code).catch(() => {}); toast('已复制') }}>复制</Button>
                    <Button variant="ghost" onClick={() => revoke.mutate(c.code)} disabled={revoke.isPending}>撤销</Button>
                  </>
                )}
              </div>
            ))}
            {q.data && q.data.length === 0 && <div className={s.desc}>还没有邀请码，点上方按钮生成。</div>}
          </div>
        )}
      </div>
    </Card>
  )
}

export default function AdminPage() {
  const { user } = useAuth()
  return (
    <div className={s.wrap}>
      <PageHeader title="管理中心" sub={user?.is_admin ? '管理员' : undefined} />
      <SiteCard />
      <UsersCard />
      <InvitesCard />
    </div>
  )
}
