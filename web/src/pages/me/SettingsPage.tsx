import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { UserPrefs } from '@/api/types'
import { getReadingSize, setReadingSize, useTheme } from '@/app/theme'
import { Button, Card, ErrorState, Field, Icon, Input, PageHeader, Segmented, Spinner, useToast } from '@/ui'
import s from './me.module.css'

type Form = Pick<UserPrefs, 'daily_goal' | 'weak_min_samples' | 'weak_max_rate'>
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, Math.round(v) || lo))

function PrefsCards({ prefs }: { prefs: UserPrefs }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [base, setBase] = useState<Form>(prefs)
  const [f, setF] = useState<Form>(prefs)
  const [justSaved, setJustSaved] = useState(false)
  const dirty = f.daily_goal !== base.daily_goal
    || f.weak_min_samples !== base.weak_min_samples || f.weak_max_rate !== base.weak_max_rate
  const set = <K extends keyof Form>(k: K, v: Form[K]) => { setF((o) => ({ ...o, [k]: v })); setJustSaved(false) }
  const save = useMutation({
    mutationFn: () => api.savePrefs(f),
    onSuccess: (r) => { setBase(r); setF(r); setJustSaved(true); qc.invalidateQueries({ queryKey: ['today'] }); toast('设置已保存') },
    onError: (e: Error) => toast(e.message, true),
  })
  const pct = Math.round(f.weak_max_rate * 100)
  return (
    <>
      <Card title="学习目标">
        <div className={s.group}>
          <Field label="每日目标题量" hint="范围 5 ~ 500 题">
            <div className={s.stepper}>
              <Button onClick={() => set('daily_goal', clamp(f.daily_goal - 5, 5, 500))} aria-label="减少">−</Button>
              <Input type="number" min={5} max={500} value={f.daily_goal}
                onChange={(e) => set('daily_goal', clamp(Number(e.target.value), 5, 500))} />
              <Button onClick={() => set('daily_goal', clamp(f.daily_goal + 5, 5, 500))} aria-label="增加"><Icon name="plus" size={14} /></Button>
            </div>
          </Field>
          <Field label="考研倒计时">
            <div className={s.desc}>{prefs.exam_date ?? '未设置'}（由管理员统一设置）</div>
          </Field>
        </div>
      </Card>
      <Card title="薄弱点分析阈值">
        <div className={s.group}>
          <p className={s.sectionHint}>自定义系统如何识别你的薄弱章节</p>
          <Field label="最少样本数">
            <div className={s.setRow}>
              <input type="range" min={3} max={50} value={f.weak_min_samples} aria-label="最少样本数"
                onChange={(e) => set('weak_min_samples', clamp(Number(e.target.value), 3, 50))} />
              <span className={s.val}>{f.weak_min_samples} 题</span>
            </div>
          </Field>
          <Field label="正确率上限">
            <div className={s.setRow}>
              <input type="range" min={30} max={90} step={5} value={pct} aria-label="正确率上限"
                onChange={(e) => set('weak_max_rate', clamp(Number(e.target.value), 30, 90) / 100)} />
              <span className={s.val}>{pct}%</span>
            </div>
          </Field>
          <div className={s.desc}>某章节至少做 {f.weak_min_samples} 题且正确率低于 {pct}% 时，将被识别为薄弱点。</div>
        </div>
      </Card>
      <div className={s.saveBar}>
        {justSaved && !dirty && <span className={s.saved}><Icon name="check" size={13} /> 已保存</span>}
        <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? '保存中…' : '保存'}
        </Button>
      </div>
    </>
  )
}

function Appearance() {
  const { theme, toggle } = useTheme()
  const [size, setSize] = useState(getReadingSize)
  useEffect(() => { setReadingSize(size) }, [size])
  return (
    <Card title="外观">
      <div className={s.group}>
        <Field label="主题">
          <Segmented value={theme} onChange={(v) => v !== theme && toggle()}
            options={[{ value: 'light', label: '亮色' }, { value: 'dark', label: '暗色' }]} />
        </Field>
        <Field label="阅读字号">
          <div className={s.setRow}>
            <input type="range" min={13} max={22} value={size} aria-label="阅读字号" onChange={(e) => setSize(Number(e.target.value))} />
            <span className={s.val}>{size}px</span>
          </div>
        </Field>
        <div className={`${s.sample} rich`}>
          <p>心力衰竭是各种心脏疾病导致心脏收缩和（或）舒张功能障碍，使心排血量不能满足机体代谢需要的临床综合征。</p>
        </div>
      </div>
    </Card>
  )
}

function PasswordCard() {
  const toast = useToast()
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const save = useMutation({
    mutationFn: () => api.changePassword({ old_password: oldPw, new_password: newPw }),
    onSuccess: () => {
      setOldPw(''); setNewPw(''); setNewPw2('')
      toast('密码已修改，其他设备的登录已失效')
    },
    onError: (e: Error) => toast(e.message, true),
  })
  const ok = oldPw.length > 0 && newPw.length >= 8 && newPw === newPw2
  return (
    <Card title="修改密码">
      <div className={s.group}>
        <Field label="原密码">
          <Input type="password" autoComplete="current-password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
        </Field>
        <Field label="新密码" hint="至少 8 位">
          <Input type="password" autoComplete="new-password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
        </Field>
        <Field label="确认新密码">
          <Input type="password" autoComplete="new-password" value={newPw2} onChange={(e) => setNewPw2(e.target.value)} />
        </Field>
        {newPw2 && newPw !== newPw2 && <div className={s.desc}>两次输入的新密码不一致</div>}
        <div className={s.saveBar}>
          <Button variant="primary" disabled={!ok || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? '提交中…' : '修改密码'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

function Version() {
  const q = useQuery({ queryKey: ['version'], queryFn: api.version })
  return (
    <Card title="版本信息">
      {q.isLoading ? <Spinner /> : q.isError || !q.data ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
        <div className={s.version}><div>当前构建号：<strong>{q.data.build}</strong></div><div className={s.desc}>{q.data.note || '暂无更新说明'}</div></div>
      )}
    </Card>
  )
}


export default function SettingsPage() {
  const q = useQuery({ queryKey: ['prefs'], queryFn: api.prefs, staleTime: 0, gcTime: 0 })
  return (
    <div className={s.wrap}>
      <PageHeader title="学习设置" />
      {q.isLoading ? <Spinner /> : q.isError || !q.data ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : <PrefsCards prefs={q.data} />}
      <Appearance />
      <PasswordCard />
      <Version />
    </div>
  )
}
