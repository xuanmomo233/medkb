import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { Button, HtmlView, Modal, Spinner } from '@/ui'
import s from './run.module.css'

export default function CardSources({ id }: { id: number }) {
  const [open, setOpen] = useState(false)
  const [index, setIndex] = useState(0)
  const q = useQuery({ queryKey: ['card-sources', id], queryFn: () => api.cardSources(id), enabled: open })
  const item = q.data?.[index]
  return (
    <>
      <Button size="sm" onClick={() => { setIndex(0); setOpen(true) }}>源题详解</Button>
      {open && <Modal title="源题详解" onClose={() => setOpen(false)}>
        {q.isPending && <Spinner />}
        {q.isError && <p>源题加载失败 <Button onClick={() => void q.refetch()}>重试</Button></p>}
        {q.isSuccess && q.data.length === 0 && <p>本卡暂无关联源题</p>}
        {item && <>
          <p>{item.qid} · {item.chapter} · {index + 1} / {q.data!.length}</p>
          {item.parent_html && <HtmlView html={item.parent_html} />}
          <HtmlView html={item.stem_html} />
          {item.options_html.map((html, i) => <div key={i}><span>{String.fromCharCode(65 + i)}.</span> <HtmlView html={html} /></div>)}
          <p>正确答案：{item.answer || '暂无'}</p>
          <HtmlView html={item.analysis_html || '<p>本题暂无解析</p>'} />
          <div className={s.sActions}>
            <Button disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>上一题</Button>
            <Button disabled={index >= q.data!.length - 1} onClick={() => setIndex((i) => i + 1)}>下一题</Button>
          </div>
        </>}
      </Modal>}
    </>
  )
}
