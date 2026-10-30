import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PlanItem, PlanToday } from '@/api/types'
import { Badge, Button, Card, EmptyState, Icon, Modal, ProgressBar, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import PlanDay from './PlanDay'
import PlanSetup from './PlanSetup'
import { invalidateStudy } from './invalidateStudy'
import { planDayDisplay, planTodayBreakdown } from './planTodayBreakdown.mjs'
import s from './today.module.css'

const ratio = (a: number, b: number) => (b ? (a / b) * 100 : 0)

function ItemRow({ it }: { it: PlanItem }) {
  const pct = ratio(it.card_done + it.question_done, it.cards + it.questions)
  return (
    <li>
      <div className={`${s.planRow} ${it.done ? s.planDone : ''}`}>
        {it.done && <Icon name="check" size={13} />}
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
  const todayCards = p.today_cards
  const todayQ = p.today_questions
  const today = planTodayBreakdown(p)
  const days = (p.day_summaries ?? []).filter((d) => d.cards + d.questions > 0)
  const sections = p.today_sections ?? []
  return (
    <div className={s.stack}>
      {p.finished ? (
        <EmptyState icon="trophy" text={`${p.total_days} 天计划已全部完成，太棒了！`}
          action={<Button variant="primary" onClick={onEdit}>设置新计划</Button>} />
      ) : (
        <>
          <div className={s.rowBetween}>
            <div>
              <span className={s.sub}>第 </span><span className={s.big}>{p.day_no}</span>
              <span className={s.sub}> / {p.total_days} 天 · 当前日期 {today.date} · 剩 {p.days_left} 天 · 还有 {p.remaining} 章</span>
            </div>
            <Badge tone="brand">今日执行总数 {today.total} 项</Badge>
          </div>
          <p className={s.meta}>顺延 {today.overdue} 项 · 今天到期 {today.dueToday} 项 · {todayCards} 卡 · {todayQ} 题</p>
          {sections.length > 0 ? (
            <>
              <p className={s.sub}>今日待做 · 每项任务只计一次</p>
              <details><summary className={s.sub}>查看今日章节（{sections.length}）</summary><ul className={s.list}>
                {sections.map((i) => (
                  <li key={i.key} className={s.planRow}>
                    <span className={s.itemTitle}>{i.label}</span>
                    <span className={s.meta}>{i.cards} 卡 · {i.questions} 题</span>
                  </li>
                ))}
              </ul></details>
              <div className={s.actions}>
                <Button variant="primary" disabled={!todayCards} onClick={() => nav('/cards/run?plan_day=1')}>继续背卡（{todayCards}）</Button>
                <Button disabled={!todayQ} onClick={() => nav('/quiz/run?plan_day=1')}>继续刷题（{todayQ}）</Button>
                <Button variant="ghost" onClick={onEdit}>修改计划</Button>
              </div>
            </>
          ) : (
            <EmptyState text="今天的任务已完成，后续安排见下方"
              action={<Button variant="primary" onClick={onEdit}>调整计划</Button>} />
          )}
        </>
      )}
      {days.length > 0 && (
        <details><summary className={s.sub}>查看每日安排</summary><ul className={s.list} aria-label="剩余天数">
          {days.map((d) => (
            <li key={d.date}>
              <button type="button" className={`${s.planRow} ${d.no === 1 ? s.planNow : ''}`} aria-expanded={open === d.no}
                aria-label={planDayDisplay(p, d.no, d.date)}
                onClick={() => setOpen(open === d.no ? null : d.no)}>
                <span className={s.planNo}>D{p.day_no + d.no - 1}</span>
                <span className={s.itemTitle}>{d.no === 1 ? '今天' : d.no === 2 ? '明天' : d.no === 3 ? '后天' : ''}{d.no <= 3 ? ` · ${d.date}` : d.date}</span>
                <span className={s.meta}>{d.cards} 卡 · {d.questions} 题{d.overdue_cards + d.overdue_questions > 0 ? `（含顺延 ${d.overdue_cards} 卡 · ${d.overdue_questions} 题）` : ''}</span>
                <span aria-hidden="true"><Icon name="chevDown" size={13} /></span>
              </button>
              {open === d.no && <PlanDay n={d.no} />}
            </li>
          ))}
        </ul></details>
      )}
      <details className={s.planTotals}>
        <summary>全章累计进度（章节可能共享题目，不等于今日任务量）</summary>
        <ul className={s.list}>{p.items.map((i) => <ItemRow key={i.key} it={i} />)}</ul>
      </details>
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
      void invalidateStudy(qc)
    },
    onError: (e) => toast(e instanceof Error ? e.message : '操作失败', true),
  })
  return (
    <Card title="学习计划">
      <Async q={q} height={260}>
        {(p) => !p.configured
          ? <EmptyState icon="calendar" text="还没有学习计划，自己选内容定天数" action={<Button variant="primary" onClick={() => setSetup(true)}>设置学习计划</Button>} />
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
