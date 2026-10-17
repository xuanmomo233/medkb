import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Button } from '@/ui'
import { keys } from './queries'
import { schedulePath } from './schedulePath'
import s from './today.module.css'

export default function ScheduleNavigation() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const id = Number(params.get('schedule_item'))
  const q = useQuery({ queryKey: keys.schedule, queryFn: api.scheduleToday, enabled: id > 0 })
  if (!(id > 0)) return null
  const items = q.data?.items ?? []
  const index = items.findIndex((item) => item.id === id)
  const next = index >= 0 ? items.slice(index + 1).find((item) => !item.done) : undefined
  return (
    <nav className={s.rowBetween} aria-label="日程任务切换">
      <Button size="sm" disabled={index <= 0} onClick={() => nav(schedulePath(items[index - 1]), { replace: true })}>上一项日程</Button>
      <span>{index >= 0 ? `日程 ${index + 1} / ${items.length}${items[index].done ? ' · 已完成' : ''}` : '今日日程'}</span>
      {next
        ? <Button size="sm" onClick={() => nav(schedulePath(next), { replace: true })}>下一项日程</Button>
        : <Button size="sm" onClick={() => nav('/')}>返回日程</Button>}
    </nav>
  )
}
