import { useState } from 'react'
import { api } from '@/api/endpoints'
import type { ContentCitation, ContentCitationInput } from '@/api/types'
import { Button, Modal, useToast } from '@/ui'
import CitationEditor from './CitationEditor'
import { citationInputs } from './citationHelpers'
import s from './notes.module.css'

export default function CitationEditSheet({ targetType, targetId, initial, open, onClose, onSaved, subject }: {
  targetType: 'chapter' | 'question' | 'card'
  targetId: number
  initial?: ContentCitation[]
  open: boolean
  onClose: () => void
  onSaved: () => void
  subject?: string
}) {
  if (!open) return null
  return <OpenEditor targetType={targetType} targetId={targetId} initial={initial} onClose={onClose} onSaved={onSaved} subject={subject} />
}

function OpenEditor({ targetType, targetId, initial, onClose, onSaved, subject }: {
  targetType: 'chapter' | 'question' | 'card'; targetId: number; initial?: ContentCitation[]; onClose: () => void; onSaved: () => void; subject?: string
}) {
  const toast = useToast()
  const [citations, setCitations] = useState<ContentCitationInput[]>(citationInputs(initial))
  const [saving, setSaving] = useState(false)
  const save = async () => {
    setSaving(true)
    try {
      await api.adminSaveCitations(targetType, targetId, citations)
      toast('教材出处已保存')
      onSaved()
      onClose()
    } catch (error) {
      toast(error instanceof Error ? error.message : '保存失败', true)
    } finally { setSaving(false) }
  }
  return <Modal sheet title="编辑教材出处" onClose={onClose}>
    <div className={s.form}>
      <CitationEditor value={citations} onChange={setCitations} subject={subject} />
      <div className={s.actions}><Button onClick={onClose}>取消</Button><Button variant="primary" disabled={saving} onClick={save}>{saving ? '保存中…' : '保存'}</Button></div>
    </div>
  </Modal>
}
