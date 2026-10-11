import { useState } from 'react'
import type { Question } from '@/api/types'
import { useAuth } from '@/app/auth'
import { AdminEditSheet, NoteSheet } from '@/features/notes'
import { Button } from '@/ui'
import s from './run.module.css'

export default function QuestionExtras({ question }: { question: Question }) {
  const { user } = useAuth()
  const [notes, setNotes] = useState(false)
  const [edit, setEdit] = useState(false)
  return (
    <div className={s.tags}>
      <Button size="sm" onClick={() => setNotes(true)}>📝 笔记 / 讨论</Button>
      {user?.is_admin && <Button size="sm" variant="ghost" onClick={() => setEdit(true)}>✏️ 编辑题目</Button>}
      <NoteSheet targetType="question" targetId={question.id} open={notes} onClose={() => setNotes(false)} />
      {user?.is_admin && <AdminEditSheet questionId={question.id} open={edit} onClose={() => setEdit(false)} />}
    </div>
  )
}
