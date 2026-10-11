import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { ScheduleToday } from '@/api/types'
import { Badge, Card, EmptyState, Icon, ProgressBar, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import s from './today.module.css'

export default function ScheduleCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: keys.schedule, queryFn: api.scheduleToday })
  const m = useMutation({
    mutationFn: api.scheduleDone,
    onMutate: async (id: number) => {
      await qc.cancelQueries({ queryKey: keys.schedule })
      const prev = qc.getQueryData<ScheduleToday>(keys.schedule)
      if (prev) {
        qc.setQueryData<ScheduleToday>(keys.schedule, {
          ...prev,
          items: prev.items.map((i) => (i.id === id ? { ...i, done: true } : i)),
          done_count: prev.done_count + (prev.items.find((i) => i.id === id)?.done ? 0 : 1),
        })
      }
      return { prev }
    },
    onError: (e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(keys.schedule, ctx.prev)
      toast(e instanceof Error ? e.message : '操作失败', true)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: keys.schedule })
      void qc.invalidateQueries({ queryKey: keys.today })
    },
  })

  return (
    <Card title="今日日程" extra={q.data && <span className={s.num}>{q.data.done_count} / {q.data.items.length || q.data.goal}</span>}>
      <Async q={q} height={220}>
        {(d) => d.items.length === 0 ? <EmptyState icon="calendar" text="今天暂无日程，去刷几道题吧" /> : (
          <div className={s.stack}>
            <ProgressBar value={d.items.length ? (d.done_count / d.items.length) * 100 : 0} tone={d.done_count >= d.items.length ? 'good' : undefined} />
            <ul className={s.list}>
              {d.items.map((it) => {
                const isQ = it.item_type === 'question'
                const to = `${isQ ? '/quiz/run' : '/cards/run'}?ids=${it.item_id}`
                return (
                  <li key={it.id} className={`${s.item} ${it.done ? s.itemDone : ''}`}>
                    <input type="checkbox" className={s.check} checked={it.done} disabled={it.done || m.isPending}
                      onChange={() => m.mutate(it.id)} aria-label={`完成：${it.title}`} />
                    <span aria-hidden="true"><Icon name={isQ ? 'quiz' : 'cards'} size={14} /></span>
                    <Link to={to} className={s.itemTitle}>{it.title}</Link>
                    <Badge tone={it.reason === 'due' ? 'info' : 'warn'}>{it.reason === 'due' ? '到期复习' : '薄弱补强'}</Badge>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </Async>
    </Card>
  )
}
