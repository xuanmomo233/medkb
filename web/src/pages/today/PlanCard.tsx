import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PlanItem, PlanToday } from '@/api/types'
import { Badge, Button, Card, EmptyState, Modal, ProgressBar, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import PlanDay from './PlanDay'
import PlanSetup from './PlanSetup'
import s from './today.module.css'

const ratio = (a: number, b: number) => (b ? (a / b) * 100 : 0)

function ItemRow({ it }: { it: PlanItem }) {
  const pct = ratio(it.card_done + it.question_done, it.cards + it.questions)
  return (
    <li>
      <div className={`${s.planRow} ${it.done ? s.planDone : ''}`}>
        <span className={s.planNo}>{it.done ? '✓' : `D${it.day}`}</span>
        <span className={s.itemTitle}>{it.label}</span>
        <span className={s.meta}>{it.card_done}/{it.cards}卡 · {it.question_done}/{it.questions}题</span>
      </div>
      <div className={s.planItemBar}><ProgressBar value={pct} /></div>
    </li>
  )
}

function Body({ p, onEdit, onRestart }: { p: PlanToday; onEdit: () => void; onRestart: () => void }) {
  const nav = useNavigate()
  const [open, setOpen] = useState<number | null>(null)
  const todayCards = p.today_items.reduce((n, i) => n + i.cards, 0)
  const todayQ = p.today_items.reduce((n, i) => n + i.questions, 0)
  const days = [...new Set(p.items.filter((i) => i.day).map((i) => i.day!))].sort((a, b) => a - b)
  return (
    <div className={s.stack}>
      {p.finished ? (
        <EmptyState icon="🎉" text={`${p.total_days} 天计划已全部完成，太棒了！`}
          action={<Button variant="primary" onClick={onEdit}>设置新计划</Button>} />
      ) : (
        <>
          <div className={s.rowBetween}>
            <div>
              <span className={s.sub}>第 </span><span className={s.big}>{p.day_no}</span>
              <span className={s.sub}> / {p.total_days} 天 · 剩 {p.days_left} 天 · 还有 {p.remaining} 章</span>
            </div>
            <Badge tone="brand">{p.today_items.length} 章</Badge>
          </div>
          {p.today_items.length > 0 ? (
            <>
              <ul className={s.list}>
                {p.today_items.map((i) => <ItemRow key={i.key} it={i} />)}
              </ul>
              <div className={s.actions}>
                <Button variant="primary" onClick={() => nav('/cards/run?plan_day=1')}>开始背卡（{todayCards}）</Button>
                <Button onClick={() => nav('/quiz/run?plan_day=1')}>开始刷题（{todayQ}）</Button>
                <Button variant="ghost" onClick={onEdit}>修改计划</Button>
              </div>
            </>
          ) : (
            <EmptyState text="今天没有安排，全部已完成或在剩余天数中排布完毕"
              action={<Button variant="primary" onClick={onEdit}>调整计划</Button>} />
          )}
        </>
      )}
      {days.length > 0 && (
        <ul className={s.list} aria-label="剩余天数">
          {days.map((d) => (
            <li key={d}>
              <button type="button" className={`${s.planRow} ${d === 1 ? s.planNow : ''}`} aria-expanded={open === d}
                onClick={() => setOpen(open === d ? null : d)}>
                <span className={s.planNo}>{d === 1 ? '今' : `D${d}`}</span>
                <span className={s.itemTitle}>{p.items.filter((i) => i.day === d).map((i) => i.part).join('、')}</span>
                <span className={s.meta}>{p.items.filter((i) => i.day === d).length} 章</span>
                <span aria-hidden="true">{open === d ? '▾' : '▸'}</span>
              </button>
              {open === d && <PlanDay n={d} />}
            </li>
          ))}
        </ul>
      )}
      <div className={s.actions}>
        <Button variant="ghost" onClick={onRestart}>重新开始计划</Button>
      </div>
    </div>
  )
}

export default function PlanCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  const [setup, setSetup] = useState(false)
  const q = useQuery({ queryKey: keys.plan, queryFn: api.plan })
  const m = useMutation({
    mutationFn: api.planRestart,
    onSuccess: () => {
      setConfirm(false)
      toast('计划已重新开始，剩余内容从今天起重新均分')
      void qc.invalidateQueries({ queryKey: keys.plan })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '操作失败', true),
  })
  return (
    <Card title="学习计划">
      <Async q={q} height={260}>
        {(p) => !p.configured
          ? <EmptyState icon="📋" text="还没有学习计划，自己选内容定天数" action={<Button variant="primary" onClick={() => setSetup(true)}>设置学习计划</Button>} />
          : <Body p={p} onEdit={() => setSetup(true)} onRestart={() => setConfirm(true)} />}
      </Async>
      {setup && <PlanSetup onClose={() => setSetup(false)} />}
      {confirm && (
        <Modal title="重新开始计划" onClose={() => setConfirm(false)}>
          <p>剩余内容将从今天重新均分到 {q.data?.total_days ?? ''} 天里。确定继续吗？</p>
          <div className={s.actions}>
            <Button onClick={() => setConfirm(false)}>取消</Button>
            <Button variant="danger" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending ? '处理中…' : '确认重新开始'}</Button>
          </div>
        </Modal>
      )}
    </Card>
  )
}
