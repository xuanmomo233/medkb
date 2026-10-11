import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { fmtTime } from '@/features/notes'
import { Badge, Button, EmptyState, ErrorState, PageHeader, Spinner, useToast } from '@/ui'
import s from './me.module.css'

export default function MyNotesPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['notes', 'mine'], queryFn: api.notesMine })
  const del = useMutation({
    mutationFn: (id: number) => api.noteDelete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notes'] }); toast('已删除') },
    onError: (e: Error) => toast(e.message, true),
  })
  const list = [...(q.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at))
  return (
    <div className={s.wrap}>
      <PageHeader title="我的笔记" sub={q.data ? `${q.data.length} 条` : undefined} />
      {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> :
        !list.length ? (
          <EmptyState icon="📝" text="还没有笔记，刷题或背卡时点「笔记」记录理解" action={<Button variant="primary" onClick={() => nav('/quiz')}>去刷题</Button>} />
        ) : (
          <div className={s.list}>
            {list.map((n) => (
              <div key={n.id} className={s.note} role="link" tabIndex={0}
                onClick={() => nav(n.target_type === 'question' ? `/quiz/run?ids=${n.target_id}` : `/cards/run?ids=${n.target_id}`)}
                onKeyDown={(e) => e.key === 'Enter' && nav(n.target_type === 'question' ? `/quiz/run?ids=${n.target_id}` : `/cards/run?ids=${n.target_id}`)}>
                <div className={s.noteHead}>
                  <Badge tone={n.target_type === 'question' ? 'info' : 'brand'}>{n.target_type === 'question' ? '题目' : '卡片'}</Badge>
                  {n.is_public && <Badge>公开</Badge>}
                  <span>{fmtTime(n.created_at)}</span>
                  <span className={s.grow} />
                  <Button variant="ghost" size="sm" disabled={del.isPending}
                    onClick={(e) => { e.stopPropagation(); if (window.confirm('确定删除这条笔记？')) del.mutate(n.id) }}>删除</Button>
                </div>
                {n.stem_preview && <div className={s.preview}>{n.stem_preview}</div>}
                <div className={s.noteBody}>{n.body}</div>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}
