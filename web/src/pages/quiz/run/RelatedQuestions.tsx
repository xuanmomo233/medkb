import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Badge, Button } from '@/ui'
import s from './run.module.css'

export default function RelatedQuestions({ id }: { id: number }) {
  const nav = useNavigate()
  const q = useQuery({ queryKey: ['related-questions', id], queryFn: () => api.relatedQuestions(id) })
  return (
    <section aria-label="同类题巩固">
      <div className={s.sectionTitle}>同类题巩固</div>
      {q.isPending && <p>正在查找同类题…</p>}
      {q.isError && <p>同类题加载失败 <Button size="sm" onClick={() => void q.refetch()}>重试</Button></p>}
      {q.isSuccess && q.data.length === 0 && <p>暂无未做的同类题推荐</p>}
      {q.data?.map((item) => (
        <div key={item.id} className={s.related}>
          <div className={s.tags}>
            <Badge tone="info">{item.label}</Badge>
            <Badge>{item.in_plan ? '计划内待做' : '未做'}</Badge>
          </div>
          <p>{item.stem}</p>
          {item.reason && <p>{item.reason}</p>}
          <Button size="sm" onClick={() => nav(`/quiz/run?ids=${item.id}&fresh=1`)}>练这一题</Button>
        </div>
      ))}
    </section>
  )
}
