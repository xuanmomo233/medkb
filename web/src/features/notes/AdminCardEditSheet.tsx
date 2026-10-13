import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { AdminCard, AdminCardPatch } from '@/api/types'
import { useAuth } from '@/app/auth'
import { Button, ErrorState, Field, Input, Modal, Spinner, Textarea, useToast } from '@/ui'
import s from './notes.module.css'

interface Props { cardId: number; open: boolean; onClose: () => void; onSaved?: () => void }

function Editor({ data, id, onClose, onSaved }: { data: AdminCard; id: number; onClose: () => void; onSaved?: () => void }) {
  const toast = useToast()
  const [section, setSection] = useState(data.section)
  const [term, setTerm] = useState(data.term)
  const [hint, setHint] = useState(data.hint)
  const [body, setBody] = useState(data.body)
  const [saving, setSaving] = useState(false)

  const patch: AdminCardPatch = {}
  if (section !== data.section) patch.section = section
  if (term !== data.term) patch.term = term
  if (hint !== data.hint) patch.hint = hint
  if (body !== data.body) patch.body = body
  const dirty = Object.keys(patch).length > 0

  const save = async () => {
    setSaving(true)
    try {
      await api.adminSaveCard(id, patch)
      toast('已保存')
      onSaved?.()
      onClose()
    } catch (e) {
      toast(e instanceof Error ? e.message : '保存失败', true)
    } finally { setSaving(false) }
  }

  return (
    <div className={s.form}>
      <Field label="分节"><Input value={section} onChange={(e) => setSection(e.target.value)} /></Field>
      <Field label="标题"><Input value={term} onChange={(e) => setTerm(e.target.value)} /></Field>
      <Field label="提示"><Textarea value={hint} onChange={(e) => setHint(e.target.value)} /></Field>
      <Field label="正文（Markdown 原文）"><Textarea className={s.mono} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
      <div className={s.actions}>
        <Button onClick={onClose}>取消</Button>
        <Button variant="primary" disabled={!dirty || saving} onClick={save}>{saving ? '保存中…' : '保存'}</Button>
      </div>
    </div>
  )
}

export default function AdminCardEditSheet({ cardId, open, onClose, onSaved }: Props) {
  const { user } = useAuth()
  if (!open || !user?.is_admin) return null
  return <OpenEditor cardId={cardId} open={open} onClose={onClose} onSaved={onSaved} />
}

function OpenEditor({ cardId, onClose, onSaved }: Props) {
  const card = useQuery({ queryKey: ['admin-card', cardId], queryFn: () => api.adminCard(cardId), gcTime: 0, refetchOnWindowFocus: false })
  return (
    <Modal sheet title={`编辑卡片 #${cardId}`} onClose={onClose}>
      {card.isLoading ? <Spinner /> : card.isError || !card.data ? <ErrorState error={card.error} onRetry={() => card.refetch()} /> :
        <Editor data={card.data} id={cardId} onClose={onClose} onSaved={onSaved} />}
    </Modal>
  )
}
