import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { SearchHit, SearchKind } from '@/api/types'
import { Badge, Button, EmptyState, ErrorState, Icon, Input, PageHeader, Segmented, Spinner } from '@/ui'
import Highlight from './Highlight'
import { useLoad } from './useLoad'
import s from './search.module.css'

type Kind = SearchKind | 'all'
const KINDS: { value: Kind; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'question', label: '题目' },
  { value: 'card', label: '考点' },
  { value: 'chapter', label: '章节' },
]
const KIND_META: Record<SearchKind, { label: string; tone: 'info' | 'warn' | 'brand' }> = {
  question: { label: '题目', tone: 'info' },
  card: { label: '考点', tone: 'warn' },
  chapter: { label: '章节', tone: 'brand' },
}
const HOT = ['心力衰竭', '肺炎链球菌', '消化性溃疡', '糖尿病酮症', '急性胰腺炎', '酶的竞争性抑制']

const target = (h: SearchHit) =>
  h.kind === 'question' ? `/quiz/run?ids=${h.id}` : h.kind === 'card' ? `/cards/run?ids=${h.id}` : `/browse/chapter/${h.id}`

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = (params.get('q') ?? '').trim()
  const kindParam = params.get('kind')
  const kind: Kind = kindParam === 'question' || kindParam === 'card' || kindParam === 'chapter' ? kindParam : 'all'
  const [input, setInput] = useState(q)
  const [prevQ, setPrevQ] = useState(q)
  if (prevQ !== q) { setPrevQ(q); setInput(q) }

  const fetcher = useCallback(() => api.search(q, kind === 'all' ? undefined : kind), [q, kind])
  const { data: hits, error, reload } = useLoad(q ? fetcher : null)

  const update = (nq: string, nk: Kind) => {
    const p = new URLSearchParams()
    if (nq) p.set('q', nq)
    if (nk !== 'all') p.set('kind', nk)
    setParams(p)
  }
  const submit = (e: FormEvent) => { e.preventDefault(); update(input.trim(), kind) }

  return (
    <div className={s.wrap}>
      <PageHeader title="搜索" sub="题目、考点与章节全文检索" />
      <form className={s.bar} onSubmit={submit}>
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="输入关键词，如：心力衰竭" aria-label="搜索关键词" autoFocus />
        <Button variant="primary" type="submit">搜索</Button>
      </form>
      <div className={s.kinds}><Segmented value={kind} options={KINDS} onChange={(k) => update(q, k)} /></div>

      {!q ? (
        <div className={s.guide}>
          <EmptyState icon="search" text="输入关键词开始搜索" />
          <div className={s.hot}>
            <span className={s.hotLabel}>热门检索</span>
            {HOT.map((w) => <button key={w} type="button" className={s.chip} onClick={() => update(w, kind)}>{w}</button>)}
          </div>
        </div>
      ) : error ? <ErrorState error={error} onRetry={reload} />
        : !hits ? <Spinner />
        : hits.length === 0 ? <EmptyState icon="search" text={`没有找到与「${q}」相关的内容`} />
        : (
          <>
            <div className={s.count}>共 {hits.length} 条结果</div>
            <ul className={s.list}>
              {hits.map((h) => (
                <li key={`${h.kind}-${h.id}`}>
                  <Link to={target(h)} className={s.hit}>
                    <div className={s.hitHead}>
                      <Badge tone={KIND_META[h.kind].tone}>{KIND_META[h.kind].label}</Badge>
                      <span className={s.hitTitle}><Highlight text={h.title} q={q} /></span>
                      <span className={s.states}>
                        {h.state === 'mastered' && <Badge tone="good">已掌握</Badge>}
                        {h.state === 'again' && <Badge tone="bad">错题</Badge>}
                        {h.state === 'plan' && <Badge tone="info">计划中</Badge>}
                        {h.starred && <span className={s.star} title="已收藏"><Icon name="star" size={13} fill /></span>}
                      </span>
                    </div>
                    {h.snippet && <p className={s.snippet}><Highlight text={h.snippet} q={q} /></p>}
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
    </div>
  )
}
