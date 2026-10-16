import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { AdminQuestion, AdminQuestionPatch, ContentCitationInput } from '@/api/types'
import { useAuth } from '@/app/auth'
import { Button, ErrorState, Field, Input, Modal, Spinner, useToast } from '@/ui'
import MarkdownEditor from './MarkdownEditor'
import CitationEditor from './CitationEditor'
import { citationInputs, sameCitations } from './citationHelpers'
import s from './notes.module.css'

interface Props { questionId: number; open: boolean; onClose: () => void; onSaved?: () => void }

const splitTags = (v: string) => v.split(/[,，]/).map((t) => t.trim()).filter(Boolean)
const splitOptions = (v: string) => v.split(/\r?\n/).map((option) => option.replace(/^[A-J][.、．]\s*/i, '').trim())

function Editor({ data, id, onClose, onSaved }: { data: AdminQuestion; id: number; onClose: () => void; onSaved?: () => void }) {
  const toast = useToast()
  const [stem, setStem] = useState(data.stem)
  const [system, setSystem] = useState(data.system)
  const [options, setOptions] = useState(data.options.join('\n'))
  const [answer, setAnswer] = useState(data.answer)
  const [tags, setTags] = useState(data.tags.join(', '))
  const [analysis, setAnalysis] = useState(data.analysis)
  const originalCitations = citationInputs(data.citations)
  const [citations, setCitations] = useState<ContentCitationInput[]>(originalCitations)
  const [saving, setSaving] = useState(false)

  const patch: AdminQuestionPatch = {}
  if (stem !== data.stem) patch.stem = stem
  if (system !== data.system) patch.system = system
  const newOptions = splitOptions(options)
  if (newOptions.join('\n') !== data.options.join('\n')) patch.options = newOptions
  if (answer !== data.answer) patch.answer = answer
  const newTags = splitTags(tags)
  if (newTags.join('\n') !== data.tags.join('\n')) patch.tags = newTags
  if (analysis !== data.analysis) patch.analysis = analysis
  if (!sameCitations(citations, originalCitations)) patch.citations = citations
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
      <MarkdownEditor label="题干（Markdown 原文）" value={stem} onChange={setStem} kind="markdown" />
      <Field label="选项" hint="每行一个选项；可粘贴 A. / B. 前缀，保存时会自动去除"><textarea className={s.textarea} value={options} onChange={(e) => setOptions(e.target.value)} rows={Math.max(4, data.options.length)} /></Field>
      <Field label="正确答案" hint="单选填 A；多选连续填写字母，例如 AC"><Input value={answer} onChange={(e) => setAnswer(e.target.value.toUpperCase())} /></Field>
      <Field label="系统分类"><Input value={system} onChange={(e) => setSystem(e.target.value)} /></Field>
      <Field label="标签" hint="多个标签用逗号分隔"><Input value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
      <MarkdownEditor label="解析（Markdown 原文）" value={analysis} onChange={setAnalysis} kind="markdown" />
      <CitationEditor value={citations} onChange={setCitations} subject={data.subject_dir} />
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
