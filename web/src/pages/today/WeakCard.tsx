import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Card, EmptyState } from '@/ui'
import { Async } from './Async'
import { pct, toneOf } from './utils'
import s from './today.module.css'


function ago(iso: string | null) {
  if (!iso) return '未作答'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  return days <= 0 ? '今天' : `${days} 天前`
}

export default function WeakCard() {
  const q = useQuery({ queryKey: ['weakspots'], queryFn: api.weakSpots })
  return (
    <Card title="薄弱点分析">
      <Async q={q} height={200}>
        {(list) => list.length === 0 ? (
          <EmptyState icon="🎯" text="继续刷题，累计样本后将自动分析薄弱点"
            action={<Link to="/me/settings" className={s.link}>调整阈值</Link>} />
        ) : (
          <ul className={s.list}>
            {[...list].sort((a, b) => a.rate - b.rate).map((w) => (
              <li key={`${w.system}-${w.chapter}`}>
                <Link className={s.weak} to={`/quiz/run?system=${encodeURIComponent(w.system)}&chapter=${encodeURIComponent(w.chapter)}`}>
                  <div className={s.rowBetween}>
                    <span className={s.itemTitle}>{w.system} · {w.chapter}</span>
                    <span className={`${s.num} ${s[`c-${toneOf(w.rate)}`]}`}>{pct(w.rate)}%</span>
                  </div>
                  <div className={s.bar}><div className={`${s.barFill} ${s[`f-${toneOf(w.rate)}`]}`} style={{ width: `${pct(w.rate)}%` }} /></div>
                  <span className={s.meta}>做题 {w.total} · 最近作答 {ago(w.last_attempt_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Async>
    </Card>
  )
}


