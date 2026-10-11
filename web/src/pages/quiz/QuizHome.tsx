import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { QuizMode } from '@/api/types'
import { Button, Card, ErrorState, Field, Input, PageHeader, useToast } from '@/ui'
import { FACET_LEVELS, MODES, readJson, toSearch } from './lib'
import { useFacets } from './useFacets'
import s from './home.module.css'

const MODE_KEY = 'quiz.mode'
const MINS_KEY = 'quiz.mins'

function Shortcut({ icon, title, desc, disabled, onClick }: { icon: string; title: string; desc: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" className={s.shortcut} disabled={disabled} onClick={onClick}>
      <span className={s.scIcon} aria-hidden>{icon}</span>
      <span className={s.scTitle}>{title}</span>
      <span className={s.scDesc}>{desc}</span>
    </button>
  )
}

export default function QuizHome() {
  const nav = useNavigate()
  const toast = useToast()
  const { filter, facets, loading, error, choose, reset, retry } = useFacets()
  const [mode, setModeState] = useState<QuizMode>(() => {
    const m = localStorage.getItem(MODE_KEY)
    return MODES.some((x) => x.value === m) ? (m as QuizMode) : 'practice'
  })
  const [mins, setMins] = useState<string>(() => String(readJson<number>(localStorage, MINS_KEY) ?? 0))
  const [busy, setBusy] = useState(false)

  const setMode = (m: QuizMode) => { setModeState(m); localStorage.setItem(MODE_KEY, m) }
  const minsNum = Math.max(0, Math.floor(Number(mins) || 0))
  const run = (extra: Record<string, unknown> = {}) => {
    localStorage.setItem(MINS_KEY, String(minsNum))
    nav(`/quiz/run?${toSearch({ ...filter, mode, mins: mode === 'test' ? minsNum : 0, ...extra })}`)
  }

  const startMock = async () => {
    setBusy(true)
    try {
      const { ids } = await api.mock(180)
      if (!ids.length) { toast('题库暂无可用题目', true); return }
      nav(`/quiz/run?${toSearch({ ids, mode: 'test', mins: 180, title: '全真模考' })}`)
    } catch (e) {
      toast(e instanceof Error ? e.message : '生成模考失败', true)
    } finally {
      setBusy(false)
    }
  }

  const hasFilter = Object.keys(filter).length > 0
  const total = facets ? Object.values(facets.bank_group).reduce((n, v) => n + v[0], 0) : 0

  return (
    <div className={s.page}>
      <PageHeader title="刷题" sub={facets ? `题库共 ${total} 题` : undefined} />

      <Card title="刷题模式">
        <div className={s.modes} role="radiogroup" aria-label="刷题模式">
          {MODES.map((m) => (
            <button key={m.value} type="button" role="radio" aria-checked={mode === m.value}
              className={`${s.mode} ${mode === m.value ? s.modeOn : ''}`} onClick={() => setMode(m.value)}>
              <span className={s.modeName}>{mode === m.value ? '✓ ' : ''}{m.label}</span>
              <span className={s.modeDesc}>{m.desc}</span>
            </button>
          ))}
        </div>
        {mode === 'test' && (
          <div className={s.mins}>
            <Field label="限时（分钟）" hint="0 表示不限时">
              <Input type="number" inputMode="numeric" min={0} max={600} value={mins} onChange={(e) => setMins(e.target.value)} />
            </Field>
          </div>
        )}
      </Card>

      <Card title="选择范围" extra={hasFilter ? <Button size="sm" variant="ghost" onClick={reset}>清除筛选</Button> : undefined}>
        {error ? <ErrorState error={error} onRetry={retry} /> : (
          <div className={s.filters}>
            {FACET_LEVELS.map((l) => {
              const opts = Object.entries(facets?.[l.key] ?? {})
              const sum = opts.reduce((a, [, v]) => [a[0] + v[0], a[1] + v[1]], [0, 0])
              return (
                <Field key={l.key} label={l.label}>
                  <select className={s.select} value={filter[l.key] ?? ''} disabled={!facets || opts.length === 0}
                    onChange={(e) => choose(l.key, e.target.value)}>
                    <option value="">全部{opts.length ? `（${sum[1]}/${sum[0]}）` : ''}</option>
                    {opts.map(([k, v]) => <option key={k} value={k}>{k} {v[1]}/{v[0]}</option>)}
                  </select>
                </Field>
              )
            })}
          </div>
        )}
        <div className={s.actions}>
          <Button variant="primary" size="lg" disabled={loading} onClick={() => run()}>开始刷题</Button>
          <Button size="lg" disabled={loading} onClick={() => run({ shuffle: true })}>乱序刷题</Button>
          <Button size="lg" disabled={loading} onClick={() => run({ random: true, limit: 120 })}>随机抽 120</Button>
          <Button size="lg" onClick={() => nav(`/quiz/pool?${toSearch(filter)}`)}>挑选题目</Button>
        </div>
      </Card>

      <div className={s.shortcuts}>
        <Shortcut icon="🎯" title="全真模考" desc="180 题 · 限时 180 分钟" disabled={busy} onClick={startMock} />
        <Shortcut icon="📕" title="错题本" desc="按章节回顾错题" onClick={() => nav('/quiz/wrongbook')} />
        <Shortcut icon="📊" title="成绩记录" desc="测试与模考成绩" onClick={() => nav('/quiz/exams')} />
        <Shortcut icon="⭐" title="收藏题" desc="集中复习收藏" onClick={() => nav(`/quiz/run?${toSearch({ starred: true, mode })}`)} />
      </div>
    </div>
  )
}
