
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Button, EmptyState, ErrorState, PageHeader, Spinner } from '@/ui'
import { fmtTime, toSearch } from './lib'
import s from './list.module.css'
import { useAsync } from './useAsync'

export default function WrongBook() {
  const nav = useNavigate()
  const { data: groups, error, retry: load } = useAsync(api.wrongbook)
  const total = groups?.reduce((n, g) => n + g.count, 0) ?? 0

  return (
    <div>
      <PageHeader title="错题本" sub={groups ? `共 ${total} 道错题` : undefined}
        extra={
          <div className={s.headBtns}>
            <Button onClick={() => nav('/quiz')}>返回</Button>
            <Button variant="primary" disabled={!total} onClick={() => nav(`/quiz/run?${toSearch({ wrong: true, mode: 'practice' })}`)}>刷全部错题</Button>
          </div>
        } />
      {error ? <ErrorState error={error} onRetry={load} /> : !groups ? <Spinner /> : groups.length === 0 ? (
        <EmptyState icon="🎉" text="暂无错题，继续保持" />
      ) : (
        <div className={s.list}>
          {groups.map((g) => (
            <button key={g.chapter} type="button" className={s.item}
              onClick={() => nav(`/quiz/run?${toSearch({ wrong: true, chapter: g.chapter, mode: 'practice' })}`)}>
              <span className={s.itemMain}>
                <span className={s.itemTitle}>{g.chapter}</span>
                <span className={s.itemSub}>累计错 {g.wrong_total} 次 · 最近 {fmtTime(g.last_wrong_at)}</span>
              </span>
              <span className={s.count}>{g.count}<small>题</small></span>
              <span className={s.arrow} aria-hidden>›</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
