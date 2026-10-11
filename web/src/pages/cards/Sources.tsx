import { useCallback, useState } from 'react'
import { api } from '@/api/endpoints'
import { Badge, ErrorState, HtmlView, Spinner } from '@/ui'
import { useLoad } from '@/pages/browse/useLoad'
import s from './run.module.css'

export default function Sources({ cardId }: { cardId: number }) {
  const fetcher = useCallback(() => api.cardSources(cardId), [cardId])
  const { data: list, error, reload } = useLoad(fetcher)
  const [open, setOpen] = useState<Record<number, boolean>>({})

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!list) return <Spinner />
  if (list.length === 0) return <div className={s.srcEmpty}>该卡片暂无关联源题</div>
  return (
    <ul className={s.srcList}>
      {list.map((q, i) => {
        const isOpen = open[q.id] ?? false
        return (
          <li key={q.id} className={s.srcItem}>
            <button type="button" className={s.srcHead} aria-expanded={isOpen} onClick={() => setOpen({ ...open, [q.id]: !isOpen })}>
              <span className={s.srcNo}>{i + 1}</span>
              <span className={s.srcStem}><HtmlView html={q.stem_html} /></span>
              <Badge tone="info">{q.qid}</Badge>
            </button>
            {isOpen && (
              <div className={s.srcBody}>
                <div className={s.srcMeta}>{q.system} · {q.qid}</div>
                <HtmlView html={q.analysis_html || '<p>暂无解析</p>'} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
