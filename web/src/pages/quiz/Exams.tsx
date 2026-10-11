import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Button, EmptyState, ErrorState, PageHeader, ProgressBar, Spinner } from '@/ui'
import { fmtTime, rateTone } from './lib'
import s from './list.module.css'
import { useAsync } from './useAsync'

export default function Exams() {
  const nav = useNavigate()
  const { data: list, error, retry: load } = useAsync(api.exams)

  return (
    <div>
      <PageHeader title="成绩记录" extra={<Button onClick={() => nav('/quiz')}>返回</Button>} />
      {error ? <ErrorState error={error} onRetry={load} /> : !list ? <Spinner /> : list.length === 0 ? (
        <EmptyState icon="📝" text="还没有测试记录" action={<Button variant="primary" onClick={() => nav('/quiz')}>去测试</Button>} />
      ) : (
        <div className={s.list}>
          {list.map((e) => {
            const tone = rateTone(e.rate)
            return (
              <div key={e.id} className={s.exam}>
                <div className={s.itemMain}>
                  <span className={s.itemTitle}>{e.title}</span>
                  <span className={s.itemSub}>{fmtTime(e.created_at)} · 答对 {e.correct} / {e.total}，答错 {e.total - e.correct}</span>
                  <ProgressBar value={e.rate} tone={tone === 'warn' ? undefined : tone} />
                </div>
                <span className={`${s.rate} ${s[`rate-${tone}`]}`}>{Math.round(e.rate)}<small>%</small></span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
