import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Badge, Button, Card, ProgressBar, useToast } from '@/ui'
import { Async } from './Async'
import { keys, useTodayQuery } from './queries'
import s from './today.module.css'

export default function CheckinCard() {
  const q = useTodayQuery()
  const qc = useQueryClient()
  const toast = useToast()
  const m = useMutation({
    mutationFn: api.checkin,
    onSuccess: (r) => {
      toast(`打卡成功，已连续 ${r.streak} 天`)
      void qc.invalidateQueries({ queryKey: keys.today })
      void qc.invalidateQueries({ queryKey: keys.calendar })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '打卡失败', true),
  })
  return (
    <Card title="每日打卡">
      <Async q={q} height={150}>
        {(d) => (
          <div className={s.stack}>
            <div className={s.row}>
              <div>
                <span className={s.big}>{d.streak}</span><span className={s.sub}> 天连续打卡</span>
              </div>
              {d.checked_in ? <Badge tone="good">今日已打卡</Badge> : (
                <Button variant="primary" onClick={() => m.mutate()} disabled={m.isPending} aria-label="打卡">
                  {m.isPending ? '打卡中…' : '打卡'}
                </Button>
              )}
            </div>
            <div>
              <div className={s.rowBetween}>
                <span className={s.sub}>今日目标</span>
                <span className={s.num}>{d.done_today} / {d.daily_goal}</span>
              </div>
              <ProgressBar value={d.daily_goal ? (d.done_today / d.daily_goal) * 100 : 0} tone={d.done_today >= d.daily_goal ? 'good' : undefined} />
            </div>
          </div>
        )}
      </Async>
    </Card>
  )
}
