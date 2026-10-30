import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PlanOption } from '@/api/types'
import { Badge, Button, Input, Modal, useToast } from '@/ui'
import { Async } from './Async'
import { keys } from './queries'
import { invalidateStudy } from './invalidateStudy'
import s from './today.module.css'

export default function PlanSetup({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [daysDraft, setDays] = useState<number | null>(null)
  const [pickedDraft, setPicked] = useState<Set<string> | null>(null)
  const current = useQuery({ queryKey: keys.plan, queryFn: api.plan })
  const q = useQuery({ queryKey: ['plan-options'], queryFn: api.planOptions })
  const initialized = !!current.data
  const days = daysDraft ?? (current.data?.configured ? current.data.total_days : 10)
  const originalPicked = useMemo(() => new Set(current.data?.configured
    ? current.data.items.map((i) => `${i.subject}|${i.part}`) : []), [current.data])
  const picked = pickedDraft ?? originalPicked
  const save = useMutation({
    mutationFn: (items: { subject: string; part: string }[]) => api.planSaveConfig({ total_days: days, items }),
    onSuccess: () => {
      toast('学习计划已保存，从今天开始')
      void invalidateStudy(qc)
      onClose()
    },
    onError: (e) => toast(e instanceof Error ? e.message : '保存失败', true),
  })

  const toggle = (subject: string, part: string) => {
    const k = `${subject}|${part}`
    setPicked((prev) => {
      const n = new Set(prev ?? originalPicked)
      if (n.has(k)) n.delete(k)
      else n.add(k)
      return n
    })
  }
  const items = useMemo(() => {
    const available = new Map<string, { subject: string; part: string }>((q.data ?? []).flatMap((grp) => grp.parts.map((p) => [
      `${grp.subject}|${p.part}`, { subject: grp.subject, part: p.part },
    ] as const)))
    return [...picked].flatMap((key) => {
      const item = available.get(key)
      return item ? [item] : []
    })
  }, [q.data, picked])
  const preview = useQuery({
    queryKey: ['plan-preview', days, items],
    queryFn: () => api.planPreview({ total_days: days, items }),
    enabled: initialized && items.length > 0,
    staleTime: 0,
  })

  return (
    <Modal title="设置学习计划" onClose={onClose}>
      <p className={s.sub}>勾选章节并设定天数，已做内容沿用进度；重复副本会去重，内容或答案有差异的题目保留。未完成任务自动顺延。</p>
      <p className={s.sub}>章节标签显示库内关联量，实际工作量以下方预览为准。</p>
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
                        disabled={!initialized || save.isPending} aria-pressed={on} onClick={() => toggle(grp.subject, p.part)}>
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
      {!initialized && <p className={s.sub}>{current.isError ? '原计划加载失败，请关闭后重试。' : '正在读取原计划…'}</p>}
      {items.length > 0 && (
        <div className={s.planPreview} aria-live="polite">
          {preview.isFetching ? <p className={s.sub}>正在计算去重后的工作量…</p>
            : preview.isError ? <p className={s.sub}>工作量预览失败，暂时无法保存。<Button variant="ghost" onClick={() => void preview.refetch()}>重试</Button></p>
            : preview.data ? <>
              <p>唯一总量：{preview.data.cards} 卡 · {preview.data.questions} 题</p>
              <p>待完成：{preview.data.pending_cards} 卡 · {preview.data.pending_questions} 题</p>
              <p>每日约：{preview.data.daily_cards} 卡 · {preview.data.daily_questions} 题</p>
              {preview.data.duplicate_questions_skipped > 0 && <p className={s.sub}>已跳过 {preview.data.duplicate_questions_skipped} 个重复题目安排。</p>}
              <p className={s.sub}>病例组保持完整，每日数量可能略高于平均配额。请按可完成的工作量调整天数。</p>
            </> : null}
        </div>
      )}
      <div className={s.planSetupBar}>
        <label className={s.sub}>完成天数
          <Input type="number" min={1} max={120} value={days} onChange={(e) => setDays(Math.max(1, Math.min(120, Number(e.target.value) || 1)))} style={{ width: 76, marginLeft: 8 }} />
        </label>
        <Badge tone="brand">已选 {items.length} 章</Badge>
        <Button variant="primary" disabled={!initialized || items.length === 0 || save.isPending || preview.isFetching || !preview.data || preview.isError}
          onClick={() => save.mutate(items)}>{save.isPending ? '保存中…' : '保存计划'}</Button>
      </div>
    </Modal>
  )
}
