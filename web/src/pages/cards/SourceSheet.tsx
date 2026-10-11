import { useMemo, useState } from 'react'
import { api } from '@/api/endpoints'
import type { Question, SourceQuestion } from '@/api/types'
import { Badge, Button, HtmlView, Icon, Modal, Spinner } from '@/ui'
import OptionList from '@/pages/quiz/run/OptionList'
import { useLoad } from '@/pages/browse/useLoad'
import s from './run.module.css'

interface Props {
  list: SourceQuestion[]
  start: number
  onClose: () => void
}

function SourceBody({ src, q }: { src: SourceQuestion; q?: Question }) {
  return (
    <div className={s.srcSheet}>
      <div className={s.badges}>
        {q?.qtype && <Badge tone="brand">{q.qtype}</Badge>}
        <Badge>{src.system}</Badge>
        {q?.chapter && <Badge>{q.chapter}</Badge>}
        <span className={s.qid}>{src.qid}</span>
      </div>
      {q?.parent_html && <div className={s.parent}><HtmlView html={q.parent_html} /></div>}
      <HtmlView html={q?.stem_html || src.stem_html} className={s.stem} />
      {q && q.options_html.length > 0 && (
        <OptionList q={q} picked="" judged reveal stat={undefined} onPick={() => {}} />
      )}
      <div className={s.srcAnswer}>
        正确答案 <strong>{q?.answer || src.answer}</strong>
      </div>
      {(q?.analysis_html || src.analysis_html) ? (
        <div className={s.srcAnalysis}>
          <div className={s.sectionTitle}>解析</div>
          <HtmlView html={q?.analysis_html || src.analysis_html} />
        </div>
      ) : (
        <div className={s.srcAnalysis}><div className={s.sectionTitle}>本题暂无解析</div></div>
      )}
    </div>
  )
}

export default function SourceSheet({ list, start, onClose }: Props) {
  const [i, setI] = useState(start)
  const ids = useMemo(() => list.map((x) => x.id), [list])
  const fetcher = useMemo(() => () => api.questions({ ids }), [ids])
  const { data: qs } = useLoad(fetcher)
  const qmap = useMemo(() => new Map((qs ?? []).map((q) => [q.id, q])), [qs])
  const src = list[i]
  return (
    <Modal side title={`源题 ${i + 1} / ${list.length}`} onClose={onClose}>
      {!qs ? <Spinner /> : <SourceBody src={src} q={qmap.get(src.id)} />}
      {list.length > 1 && (
        <div className={s.srcNav}>
          <Button disabled={i === 0} onClick={() => setI(i - 1)}><Icon name="chevLeft" size={14} /> 上一题</Button>
          <span className={s.meta}>{i + 1} / {list.length}</span>
          <Button disabled={i >= list.length - 1} onClick={() => setI(i + 1)}>下一题 <Icon name="chevRight" size={14} /></Button>
        </div>
      )}
    </Modal>
  )
}
