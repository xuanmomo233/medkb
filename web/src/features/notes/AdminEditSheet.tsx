import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { AdminQuestion, AdminQuestionPatch } from '@/api/types'
import { useAuth } from '@/app/auth'
import { Button, ErrorState, Field, Input, Modal, Spinner, Textarea, useToast } from '@/ui'
import s from './notes.module.css'

interface Props { questionId: number; open: boolean; onClose: () => void; onSaved?: () => void }

const splitTags = (v: string) => v.split(/[,，]/).map((t) => t.trim()).filter(Boolean)

function Editor({ data, id, onClose, onSaved }: { data: AdminQuestion; id: number; onClose: () => void; onSaved?: () => void }) {
  const toast = useToast()
  const [stem, setStem] = useState(data.stem)
  const [system, setSystem] = useState(data.system)
  const [tags, setTags] = useState(data.tags.join(', '))
  const [analysis, setAnalysis] = useState(data.analysis)
  const [saving, setSaving] = useState(false)

  const patch: AdminQuestionPatch = {}
  if (stem !== data.stem) patch.stem = stem
  if (system !== data.system) patch.system = system
  const newTags = splitTags(tags)
  if (newTags.join('\n') !== data.tags.join('\n')) patch.tags = newTags
  if (analysis !== data.analysis) patch.analysis = analysis
  const dirty = Object.keys(patch).length > 0

  const save = async () => {
    setSaving(true)
    try {
      await api.adminSaveQuestion(id, patch)
      toast('已保存')
      onSaved?.()
      onClose()
    } catch (e) {
      toast(e instanceof Error ? e.message : '保存失败', true)
    } finally { setSaving(false) }
  }

  return (
    <div className={s.form}>
      <Field label="题干（Markdown 原文）"><Textarea className={s.mono} value={stem} onChange={(e) => setStem(e.target.value)} /></Field>
      <Field label="系统分类"><Input value={system} onChange={(e) => setSystem(e.target.value)} /></Field>
      <Field label="标签" hint="多个标签用逗号分隔"><Input value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
      <Field label="解析（Markdown 原文）"><Textarea className={s.mono} value={analysis} onChange={(e) => setAnalysis(e.target.value)} /></Field>
      <div className={s.actions}>
        <Button onClick={onClose}>取消</Button>
        <Button variant="primary" disabled={!dirty || saving} onClick={save}>{saving ? '保存中…' : '保存'}</Button>
      </div>
    </div>
  )
}

export default function AdminEditSheet({ questionId, open, onClose, onSaved }: Props) {
  const { user } = useAuth()
  if (!open || !user?.is_admin) return null
  return <OpenEditor questionId={questionId} open={open} onClose={onClose} onSaved={onSaved} />
}

function OpenEditor({ questionId, onClose, onSaved }: Props) {
  const q = useQuery({ queryKey: ['admin-question', questionId], queryFn: () => api.adminQuestion(questionId), gcTime: 0, refetchOnWindowFocus: false })
  return (
    <Modal sheet title={`管理员改题 #${questionId}`} onClose={onClose}>
      {q.isLoading ? <Spinner /> : q.isError || !q.data ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        <Editor data={q.data} id={questionId} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  )
}
