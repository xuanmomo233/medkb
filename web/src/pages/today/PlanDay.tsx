import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Async } from './Async'
import s from './today.module.css'

export default function PlanDay({ n }: { n: number }) {
  const q = useQuery({ queryKey: ['plan-day', n], queryFn: () => api.planDay(n) })
  return (
    <div className={s.planDay}>
      <Async q={q} height={80}>
        {(d) => (
          <>
            <div className={s.meta}>卡片清单</div>
            <div className={s.chips}>
              {d.cards.map((c) => <Link key={c.id} className={s.chip} to={`/cards/run?ids=${c.id}`}>{c.term}</Link>)}
              {d.cards.length === 0 && <span className={s.meta}>暂无卡片</span>}
            </div>
            <div className={s.meta}>题目分组</div>
            <div className={s.chips}>
              {d.question_groups.map((g) => (
                <Link key={g.chapter} className={s.chip} to={`/quiz/run?ids=${g.ids.join(',')}`}>{g.chapter} · {g.ids.length} 题</Link>
              ))}
              {d.question_groups.length === 0 && <span className={s.meta}>暂无题目</span>}
            </div>
          </>
        )}
      </Async>
    </div>
  )
}
