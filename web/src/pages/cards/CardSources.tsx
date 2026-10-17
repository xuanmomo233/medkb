import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Badge, Button, HtmlView, Modal, Spinner } from '@/ui'
import { QuizExercise } from '../quiz/run/QuizRun'
import s from './run.module.css'

export default function CardSources({ id }: { id: number }) {
  const [open, setOpen] = useState(false)
  const [exercise, setExercise] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['card-sources', id], queryFn: () => api.cardSources(id), enabled: open })
  return (
    <>
      <Button size="sm" onClick={() => { setExercise(null); setOpen(true) }}>源题练习与解析</Button>
      {open && <Modal title="源题详解" onClose={() => setOpen(false)}>
        {exercise ? <QuizExercise key={exercise} search={exercise} onBack={() => setExercise(null)} /> : <>
          {q.isPending && <Spinner />}
          {q.isError && <p>源题加载失败 <Button onClick={() => void q.refetch()}>重试</Button></p>}
          {q.isSuccess && q.data.length === 0 && <p>本卡暂无关联源题</p>}
          {q.data?.map((item) => <section key={item.id} className={s.srcBox}>
            <p>{item.qid} · {item.chapter} <Badge>{item.done ? '已作答' : '未作答'}</Badge></p>
            <HtmlView html={item.stem_html} />
            <div className={s.sActions}>
              <Button variant="primary" onClick={() => setExercise(`ids=${item.id}&start_id=${item.id}&mode=practice`)}>开始作答</Button>
              <Button onClick={() => setExercise(`ids=${item.id}&start_id=${item.id}&mode=recite`)}>只看解析</Button>
            </div>
          </section>)}
        </>}
      </Modal>}
    </>
  )
}
