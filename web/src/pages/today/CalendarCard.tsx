import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Button, Card } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import s from './today.module.css'

const WEEK = ['一', '二', '三', '四', '五', '六', '日']
const ym = (y: number, m: number) => `${y}-${String(m + 1).padStart(2, '0')}`

export default function CalendarCard() {
  const [now] = useState(() => new Date())
  const [cur, setCur] = useState({ y: now.getFullYear(), m: now.getMonth() })
  const month = ym(cur.y, cur.m)
  const q = useQuery({ queryKey: [...keys.calendar, month], queryFn: () => api.calendar(month) })
  const shift = (d: number) => setCur(({ y, m }) => {
    const t = new Date(y, m + d, 1)
    return { y: t.getFullYear(), m: t.getMonth() }
  })
  const offset = (new Date(cur.y, cur.m, 1).getDay() + 6) % 7
  const total = new Date(cur.y, cur.m + 1, 0).getDate()
  const isThisMonth = cur.y === now.getFullYear() && cur.m === now.getMonth()

  return (
    <Card title="打卡日历" extra={
      <span className={s.calNav}>
        <Button variant="ghost" size="sm" onClick={() => shift(-1)} aria-label="上个月">‹</Button>
        <span className={s.calTitle}>{cur.y} 年 {cur.m + 1} 月</span>
        <Button variant="ghost" size="sm" onClick={() => shift(1)} aria-label="下个月">›</Button>
      </span>
    }>
      <Async q={q} height={220}>
        {(d) => {
          const set = new Set(d.days)
          return (
            <div className={s.cal} role="grid" aria-label={`${month} 打卡日历`}>
              {WEEK.map((w) => <span key={w} className={s.calHead}>{w}</span>)}
              {Array.from({ length: offset }, (_, i) => <span key={`b${i}`} />)}
              {Array.from({ length: total }, (_, i) => {
                const day = i + 1
                const cls = [s.calDay, set.has(day) && s.calOn, isThisMonth && day === now.getDate() && s.calToday].filter(Boolean).join(' ')
                return <span key={day} className={cls} role="gridcell" aria-label={`${day} 日${set.has(day) ? '，已打卡' : ''}`}>{day}</span>
              })}
            </div>
          )
        }}
      </Async>
    </Card>
  )
}


