import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { PublicNote, TargetType } from '@/api/types'
import { Badge, Button, EmptyState, ErrorState, Icon, Modal, Segmented, Spinner, Textarea, useToast } from '@/ui'
import { fmtTime } from './time'
import s from './notes.module.css'

interface Props { targetType: TargetType; targetId: number; open: boolean; onClose: () => void }
type Tab = 'mine' | 'public'

function MineTab({ targetType, targetId }: Omit<Props, 'open' | 'onClose'>) {
  const qc = useQueryClient()
  const toast = useToast()
  const [text, setText] = useState('')
  const [pub, setPub] = useState(false)
  const key = ['notes', targetType, targetId]
  const q = useQuery({ queryKey: key, queryFn: () => api.notesOf(targetType, targetId) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['notes'] }); qc.invalidateQueries({ queryKey: ['public-notes'] }) }
  const add = useMutation({
    mutationFn: () => api.noteAdd({ target_type: targetType, target_id: targetId, body: text.trim(), is_public: pub }),
    onSuccess: () => { setText(''); refresh(); toast('已发布') },
    onError: (e: Error) => toast(e.message, true),
  })
  const del = useMutation({
    mutationFn: (id: number) => api.noteDelete(id),
    onSuccess: () => { refresh(); toast('已删除') },
    onError: (e: Error) => toast(e.message, true),
  })
  return (
    <>
      {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        !q.data?.length ? <EmptyState icon="note" text="还没有笔记，记下你的理解吧" /> : (
          <div className={s.list}>
            {q.data.map((n) => (
              <div key={n.id} className={s.item}>
                <div className={s.meta}>
                  <span>{fmtTime(n.created_at)}</span>
                  {n.is_public && <Badge tone="brand">公开</Badge>}
                  <span className={s.grow} />
                  <Button variant="ghost" size="sm" disabled={del.isPending}
                    onClick={() => window.confirm('确定删除这条笔记？') && del.mutate(n.id)}>删除</Button>
                </div>
                <div className={s.body}>{n.body}</div>
              </div>
            ))}
          </div>
        )}
      <div className={s.composer}>
        <Textarea rows={3} value={text} maxLength={2000} placeholder="写下你的笔记…" onChange={(e) => setText(e.target.value)} />
        <div className={s.row}>
          <label className={s.check}><input type="checkbox" checked={pub} onChange={(e) => setPub(e.target.checked)} />公开发布</label>
          <Button variant="primary" disabled={!text.trim() || add.isPending} onClick={() => add.mutate()}>
            {add.isPending ? '发布中…' : pub ? '公开发布' : '保存笔记'}
          </Button>
        </div>
      </div>
    </>
  )
}

function PublicTab({ targetType, targetId }: Omit<Props, 'open' | 'onClose'>) {
  const qc = useQueryClient()
  const toast = useToast()
  const key = ['public-notes', targetType, targetId]
  const q = useQuery({ queryKey: key, queryFn: () => api.publicNotes(targetType, targetId) })
  const like = useMutation({
    mutationFn: (id: number) => api.noteLike(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<PublicNote[]>(key)
      qc.setQueryData<PublicNote[]>(key, (a) => a?.map((n) => n.id === id ? { ...n, liked: !n.liked, likes: n.likes + (n.liked ? -1 : 1) } : n))
      return { prev }
    },
    onError: (e: Error, _id, ctx) => { qc.setQueryData(key, ctx?.prev); toast(e.message, true) },
  })
  if (q.isLoading) return <Spinner />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const list = [...(q.data ?? [])].sort((a, b) => b.likes - a.likes)
  if (!list.length) return <EmptyState icon="chat" text="还没有公开讨论，来发表第一条吧" />
  return (
    <div className={s.list}>
      {list.map((n) => (
        <div key={n.id} className={s.item}>
          <div className={s.meta}>
            <strong>{n.username}</strong>
            {n.mine && <Badge tone="brand">我的</Badge>}
            <span>{fmtTime(n.created_at)}</span>
            <span className={s.grow} />
            <button type="button" className={`${s.like} ${n.liked ? s.liked : ''}`} onClick={() => like.mutate(n.id)}>
              <Icon name="like" size={14} fill={n.liked} /> {n.likes}
            </button>
          </div>
          <div className={s.body}>{n.body}</div>
        </div>
      ))}
    </div>
  )
}

export default function NoteSheet({ targetType, targetId, open, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('mine')
  if (!open) return null
  return (
    <Modal sheet title="笔记与讨论" onClose={onClose}>
      <div className={s.tabs}>
        <Segmented<Tab> value={tab} onChange={setTab} options={[{ value: 'mine', label: '我的笔记' }, { value: 'public', label: '公开讨论' }]} />
      </div>
      {tab === 'mine' ? <MineTab targetType={targetType} targetId={targetId} /> : <PublicTab targetType={targetType} targetId={targetId} />}
    </Modal>
  )
}
