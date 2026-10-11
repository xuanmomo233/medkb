import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PlanToday } from '@/api/types'
import { Badge, Button, Card, EmptyState, Modal, ProgressBar, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import PlanDay from './PlanDay'
import s from './today.module.css'

const ratio = (a: number, b: number) => (b ? (a / b) * 100 : 0)

function Body({ p, onRestart }: { p: PlanToday; onRestart: () => void }) {
  const nav = useNavigate()
  const [open, setOpen] = useState<number | null>(null)
  return (
    <div className={s.stack}>
      {p.finished ? (
        <EmptyState icon="🎉" text={`${p.total_days} 天计划已全部完成，太棒了！`}
          action={<Button variant="primary" onClick={onRestart}>重新开始计划</Button>} />
      ) : (
        <>
          <div className={s.rowBetween}>
            <div>
              <span className={s.sub}>第 </span><span className={s.big}>{p.today_no}</span>
              <span className={s.sub}> / {p.total_days} 天</span>
            </div>
            <Badge tone="brand">{p.title}</Badge>
          </div>
          <div>
            <div className={s.rowBetween}><span className={s.sub}>卡片</span><span className={s.num}>{p.card_done} / {p.card_ids.length}</span></div>
            <ProgressBar value={ratio(p.card_done, p.card_ids.length)} />
          </div>
          <div>
            <div className={s.rowBetween}><span className={s.sub}>题目</span><span className={s.num}>{p.question_done} / {p.question_ids.length}</span></div>
            <ProgressBar value={ratio(p.question_done, p.question_ids.length)} />
          </div>
          <div className={s.actions}>
            <Button variant="primary" onClick={() => nav(`/cards/run?plan_day=${p.today_no}`)}>开始背卡</Button>
            <Button onClick={() => nav(`/quiz/run?plan_day=${p.today_no}`)}>开始刷题</Button>
            <Button variant="ghost" onClick={onRestart}>重新开始计划</Button>
          </div>
        </>
      )}
      <ul className={s.list} aria-label="计划总览">
        {p.overview.map((d) => (
          <li key={d.no}>
            <button type="button" className={`${s.planRow} ${d.no === p.today_no ? s.planNow : ''}`} aria-expanded={open === d.no}
              onClick={() => setOpen(open === d.no ? null : d.no)}>
              <span className={s.planNo}>D{d.no}</span>
              <span className={s.itemTitle}>{d.title}</span>
              <span className={s.meta}>{d.card_count} 卡</span>
              <span aria-hidden="true">{open === d.no ? '▾' : '▸'}</span>
            </button>
            {open === d.no && <PlanDay n={d.no} />}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function PlanCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const q = useQuery({ queryKey: keys.plan, queryFn: api.plan })
  const m = useMutation({
    mutationFn: api.planRestart,
    onSuccess: () => {
      setConfirm(false)
      toast('计划已重新开始')
      void qc.invalidateQueries({ queryKey: keys.plan })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '操作失败', true),
  })
  return (
    <Card title="学习计划">
      <Async q={q} height={260}>{(p) => <Body p={p} onRestart={() => setConfirm(true)} />}</Async>
      {confirm && (
        <Modal title="重新开始计划" onClose={() => setConfirm(false)}>
          <p>将从第 1 天重新开始，当前计划进度会被清空。确定继续吗？</p>
          <div className={s.actions}>
            <Button onClick={() => setConfirm(false)}>取消</Button>
            <Button variant="danger" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending ? '处理中…' : '确认重新开始'}</Button>
          </div>
        </Modal>
      )}
    </Card>
  )
}

