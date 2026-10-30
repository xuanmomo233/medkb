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
            {d.cards.length === 0 ? <span className={s.meta}>暂无卡片</span> : Object.entries(
              d.cards.reduce<Record<string, typeof d.cards>>((groups, card) => {
                (groups[card.part || '未分类'] ??= []).push(card)
                return groups
              }, {}),
            ).map(([part, cards]) => (
              <section key={part} className={s.planCardGroup}>
                <div className={s.planPickTitle}>{part}</div>
                <div className={s.chips}>
                  {cards.map((c) => (
                    <Link key={c.id} className={s.chip} title={c.term} to={`/cards/run?ids=${c.id}&plan_day=${n}`}>
                      {c.term}
                    </Link>
                  ))}
                </div>
              </section>
            ))}
            <div className={s.meta}>题目分组</div>
            <div className={s.chips}>
              {d.question_groups.map((g) => (
                <Link key={`${g.subject_dir}|${g.chapter}`} className={s.chip} to={`/quiz/run?ids=${g.ids.join(',')}&plan_day=${n}`}>{[g.subject_dir, g.chapter].filter(Boolean).join(' · ')} · {g.ids.length} 题</Link>
              ))}
              {d.question_groups.length === 0 && <span className={s.meta}>暂无题目</span>}
            </div>
          </>
        )}
      </Async>
    </div>
  )
}
