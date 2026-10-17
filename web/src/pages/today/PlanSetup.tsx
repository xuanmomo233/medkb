import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PlanOption } from '@/api/types'
import { Badge, Button, Input, Modal, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import s from './today.module.css'

export default function PlanSetup({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [days, setDays] = useState(10)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const q = useQuery({ queryKey: ['plan-options'], queryFn: api.planOptions })
  const save = useMutation({
    mutationFn: (items: { subject: string; part: string }[]) => api.planSaveConfig({ total_days: days, items }),
    onSuccess: () => {
      toast('学习计划已保存，从今天开始')
      void qc.invalidateQueries({ queryKey: keys.plan })
      onClose()
    },
    onError: (e) => toast(e instanceof Error ? e.message : '保存失败', true),
  })

  const toggle = (subject: string, part: string) => {
    const k = `${subject}|${part}`
    setPicked((prev) => {
      const n = new Set(prev)
      if (n.has(k)) n.delete(k)
      else n.add(k)
      return n
    })
  }
  const items = useMemo(() => {
    const out: { subject: string; part: string }[] = []
    for (const grp of q.data ?? [])
      for (const p of grp.parts)
        if (picked.has(`${grp.subject}|${p.part}`)) out.push({ subject: grp.subject, part: p.part })
    return out
  }, [q.data, picked])

  return (
    <Modal title="设置学习计划" onClose={onClose}>
      <p className={s.sub}>勾选章节并设定天数，已做内容沿用进度；同一题只安排一次，未完成任务自动顺延。</p>
      <Async q={q} height={200}>
        {(opts: PlanOption[]) => (
          <div className={s.planPick}>
            {opts.map((grp) => (
              <div key={grp.subject} className={s.planPickSubj}>
                <div className={s.planPickTitle}>{grp.subject}</div>
                <div className={s.chips}>
                  {grp.parts.map((p) => {
                    const k = `${grp.subject}|${p.part}`
                    const on = picked.has(k)
                    return (
                      <button key={k} type="button" className={`${s.chip} ${on ? s.chipOn : ''}`}
                        aria-pressed={on} onClick={() => toggle(grp.subject, p.part)}>
                        {p.part} <span className={s.meta}>{p.cards}卡·{p.questions}题</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </Async>
      <div className={s.planSetupBar}>
        <label className={s.sub}>完成天数
          <Input type="number" min={1} max={120} value={days} onChange={(e) => setDays(Math.max(1, Math.min(120, Number(e.target.value) || 1)))} style={{ width: 76, marginLeft: 8 }} />
        </label>
        <Badge tone="brand">已选 {items.length} 章</Badge>
        <Button variant="primary" disabled={items.length === 0 || save.isPending}
          onClick={() => save.mutate(items)}>{save.isPending ? '保存中…' : '保存计划'}</Button>
      </div>
    </Modal>
  )
}
