import { useCallback, useState } from 'react'
import { api } from '@/api/endpoints'
import { Badge, ErrorState, HtmlView, Icon, Spinner } from '@/ui'
import { useLoad } from '@/pages/browse/useLoad'
import SourceSheet from './SourceSheet'
import s from './run.module.css'

export default function Sources({ cardId }: { cardId: number }) {
  const fetcher = useCallback(() => api.cardSources(cardId), [cardId])
  const { data: list, error, reload } = useLoad(fetcher)
  const [open, setOpen] = useState<number | null>(null)

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!list) return <Spinner />
  if (list.length === 0) return <div className={s.srcEmpty}>该卡片暂无关联源题</div>
  return (
    <>
      <ul className={s.srcList}>
        {list.map((q, i) => (
          <li key={q.id} className={s.srcItem}>
            <button type="button" className={s.srcHead} onClick={() => setOpen(i)}>
              <span className={s.srcNo}>{i + 1}</span>
              <span className={s.srcStem}><HtmlView html={q.stem_html} /></span>
              <Badge tone="info">{q.qid}</Badge>
              <span className={s.srcGo} aria-hidden><Icon name="chevRight" size={14} /></span>
            </button>
          </li>
        ))}
      </ul>
      {open !== null && <SourceSheet list={list} start={open} onClose={() => setOpen(null)} />}
    </>
  )
}
