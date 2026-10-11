import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { PoolFilter, PoolItem, PoolPage } from '@/api/types'
import { Badge, Button, EmptyState, ErrorState, PageHeader, Spinner } from '@/ui'
import { filterFromParams, toSearch } from './lib'
import s from './pool.module.css'

const SIZE = 50
const CHIPS: { flt: PoolFilter | ''; label: string; count: (st: PoolPage['stats']) => number }[] = [
  { flt: '', label: '总数', count: (t) => t.total },
  { flt: 'done', label: '已做', count: (t) => t.done },
  { flt: 'wrong', label: '错题', count: (t) => t.wrong },
  { flt: 'starred', label: '收藏', count: (t) => t.starred },
  { flt: 'plan', label: '计划', count: (t) => t.plan },
  { flt: 'mastered', label: '掌握', count: (t) => t.mastered },
]

function StateBadges({ it }: { it: PoolItem }) {
  return (
    <span className={s.badges}>
      {it.state === 'again' && <Badge tone="bad">✗ 错</Badge>}
      {it.state === 'mastered' && <Badge tone="good">✓ 掌握</Badge>}
      {it.in_plan && <Badge tone="warn">计划</Badge>}
      {it.done && <Badge tone="info">已做</Badge>}
      {it.starred && <Badge tone="warn">★ 收藏</Badge>}
    </span>
  )
}

export default function QuizPool() {
  const [sp] = useSearchParams()
  return <PoolView key={sp.toString()} />
}

function PoolView() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const filter = useMemo(() => filterFromParams(sp), [sp])
  const [flt, setFlt] = useState<PoolFilter | ''>('')
  const [stats, setStats] = useState<PoolPage['stats'] | null>(null)
  const [items, setItems] = useState<PoolItem[]>([])
  const [more, setMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [sel, setSel] = useState<Set<number>>(new Set())
  const busy = useRef(false)
  const seq = useRef(0)

  const fetchPage = useCallback((offset: number) => {
    if (busy.current) return
    busy.current = true
    const n = ++seq.current
    setLoading(true)
    setError(null)
    api.pool({ ...filter, flt: flt || undefined, offset, size: SIZE }).then((r) => {
      if (n !== seq.current) return
      setStats(r.stats)
      setItems((a) => (offset === 0 ? r.items : [...a, ...r.items]))
      setMore(r.items.length === SIZE)
    }, (e: unknown) => { if (n === seq.current) setError(e) }).finally(() => {
      if (n === seq.current) { busy.current = false; setLoading(false) }
    })
  }, [filter, flt])

  useEffect(() => { fetchPage(0) }, [fetchPage])

  const changeFlt = (f: PoolFilter | '') => {
    busy.current = false
    setItems([])
    setSel(new Set())
    setFlt(f)
  }

  const toggle = (id: number) => setSel((a) => { const b = new Set(a); if (!b.delete(id)) b.add(id); return b })
  const allOn = items.length > 0 && items.every((i) => sel.has(i.id))
  const toggleAll = () => setSel(allOn ? new Set() : new Set(items.map((i) => i.id)))
  const runSel = () => nav(`/quiz/run?${toSearch({ ids: [...sel] })}`)
  const filterText = Object.values(filter).join(' / ')

  return (
    <div>
      <PageHeader title="挑选题目" sub={filterText || '全部题库'} extra={<Button onClick={() => nav('/quiz')}>返回</Button>} />
      <div className={s.chips}>
        {CHIPS.map((c) => (
          <button key={c.label} type="button" className={`${s.chip} ${flt === c.flt ? s.chipOn : ''}`} aria-pressed={flt === c.flt}
            onClick={() => changeFlt(c.flt)}>
            <span className={s.chipNum}>{stats ? c.count(stats) : '–'}</span>{c.label}
          </button>
        ))}
      </div>

      <div className={s.bar}>
        <label className={s.checkAll}>
          <input type="checkbox" checked={allOn} onChange={toggleAll} disabled={!items.length} /> 全选（已选 {sel.size}）
        </label>
        <Button variant="primary" disabled={!sel.size} onClick={runSel}>刷选中题目</Button>
      </div>

      {error && !items.length ? <ErrorState error={error} onRetry={() => fetchPage(0)} /> : (
        <div className={s.list}>
          {items.map((it) => (
            <label key={it.id} className={`${s.row} ${sel.has(it.id) ? s.rowOn : ''}`}>
              <input type="checkbox" checked={sel.has(it.id)} onChange={() => toggle(it.id)} />
              <span className={s.qid}>{it.qid}</span>
              <span className={s.stem} title={it.stem}>{it.stem}</span>
              <span className={s.ans}>答案 {it.answer}</span>
              <StateBadges it={it} />
              <span className={s.wrongCount}>{it.wrong_count > 0 ? `错 ${it.wrong_count} 次` : ''}</span>
            </label>
          ))}
          {loading && <Spinner />}
          {!loading && !items.length && <EmptyState text="没有符合条件的题目" />}
        </div>
      )}

      {!!error && items.length > 0 && <ErrorState error={error} onRetry={() => fetchPage(items.length)} />}
      {more && !loading && !error && (
        <div className={s.more}><Button onClick={() => fetchPage(items.length)}>加载更多</Button></div>
      )}
    </div>
  )
}
