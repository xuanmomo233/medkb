import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { CardPartIndex } from '@/api/types'
import { Badge, EmptyState, ErrorState, PageHeader, Spinner } from '@/ui'
import { useLoad } from '@/pages/browse/useLoad'
import s from './pick.module.css'

const fetchIndex = () => api.cardIndex()

export default function CardsPickPage() {
  const { data: index, error, reload } = useLoad(fetchIndex)
  const [planDay, setPlanDay] = useState<number | null>(null)
  useEffect(() => {
    api.plan().then((p) => setPlanDay(p.configured && p.today_items.length > 0 ? 1 : null), () => setPlanDay(null))
  }, [])

  const groups = useMemo(() => {
    const m = new Map<string, CardPartIndex[]>()
    for (const c of index ?? []) { const a = m.get(c.subject); if (a) a.push(c); else m.set(c.subject, [c]) }
    return [...m]
  }, [index])

  const quick = [
    { to: '/cards/run?due=1', icon: '⏰', title: '到期复习', desc: '按遗忘曲线到期的卡片' },
    { to: '/cards/run?starred=1', icon: '⭐', title: '收藏卡片', desc: '你标星的重点考点' },
    ...(planDay ? [{ to: `/cards/run?plan_day=${planDay}`, icon: '📅', title: '今日计划', desc: `第 ${planDay} 天的背卡任务` }] : []),
  ]

  return (
    <div>
      <PageHeader title="背卡" sub="翻面回忆，按记忆程度评分" />
      <div className={s.quick}>
        {quick.map((q) => (
          <Link key={q.to} to={q.to} className={s.quickItem}>
            <span className={s.quickIcon} aria-hidden>{q.icon}</span>
            <span><span className={s.quickTitle}>{q.title}</span><span className={s.quickDesc}>{q.desc}</span></span>
          </Link>
        ))}
      </div>
      {error ? <ErrorState error={error} onRetry={reload} />
        : !index ? <Spinner />
        : groups.length === 0 ? <EmptyState icon="🃏" text="暂无卡片" />
        : groups.map(([subject, parts]) => (
          <section key={subject} className={s.section}>
            <h2 className={s.subject}>{subject}<Badge>{parts.reduce((n, p) => n + p.count, 0)} 张</Badge></h2>
            <div className={s.grid}>
              {parts.map((p) => (
                <Link key={p.part} to={`/cards/run?subject=${encodeURIComponent(p.subject)}&part=${encodeURIComponent(p.part)}`} className={s.part}>
                  <span className={s.partName}>{p.part}</span>
                  <span className={s.partCount}>{p.count} 张</span>
                </Link>
              ))}
            </div>
          </section>
        ))}
    </div>
  )
}
