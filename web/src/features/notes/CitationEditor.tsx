import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { CitationStatus, ContentCitationInput } from '@/api/types'
import { Button, Field, Input, Spinner } from '@/ui'
import s from './notes.module.css'

export default function CitationEditor({ value, onChange, subject = '' }: { value: ContentCitationInput[]; onChange: (value: ContentCitationInput[]) => void; subject?: string }) {
  const catalog = useQuery({ queryKey: ['textbooks'], queryFn: api.textbooks, staleTime: 60 * 60 * 1000 })
  const update = (index: number, patch: Partial<ContentCitationInput>) =>
    onChange(value.map((item, i) => i === index ? { ...item, ...patch } : item))
  const add = () => {
    const source = catalog.data?.sources.find((item) => subject.includes(item.subject) || item.subject.includes(subject))
      ?? catalog.data?.sources[0]
    if (!source) return
    onChange([...value, { source_key: source.key, chapter: '', section: '', page_start: null, page_end: null, note: '', status: 'unverified' }])
  }
  return <section className={s.citations}>
    <div className={s.citationHead}><strong>人卫第十版教材出处</strong><Button size="sm" onClick={add} disabled={!catalog.data?.sources.length}>添加出处</Button></div>
    <p className={s.citationHint}>只填写实际核对的位置；未核对时保持“待核验”，不要猜页码。</p>
    {catalog.isLoading && <Spinner />}
    {value.map((citation, index) => <div className={s.citationRow} key={`${citation.source_key}-${index}`}>
      <label>教材<select value={citation.source_key} onChange={(event) => update(index, { source_key: event.target.value })}>
        {catalog.data?.sources.map((source) => <option value={source.key} key={source.key}>{source.subject} · 《{source.title}》{source.edition}</option>)}
      </select></label>
      <Field label="教材章节"><Input value={citation.chapter} onChange={(event) => update(index, { chapter: event.target.value })} /></Field>
      <Field label="小节"><Input value={citation.section} onChange={(event) => update(index, { section: event.target.value })} /></Field>
      <Field label="起始页"><Input type="number" min={1} value={citation.page_start ?? ''} onChange={(event) => update(index, { page_start: event.target.value ? Number(event.target.value) : null })} /></Field>
      <Field label="结束页"><Input type="number" min={1} value={citation.page_end ?? ''} onChange={(event) => update(index, { page_end: event.target.value ? Number(event.target.value) : null })} /></Field>
      <label>状态<select value={citation.status} onChange={(event) => update(index, { status: event.target.value as CitationStatus })}>
        <option value="unverified">待核验</option><option value="verified">已核验</option><option value="disputed">存在争议</option>
      </select></label>
      <Field label="说明"><Input value={citation.note} onChange={(event) => update(index, { note: event.target.value })} /></Field>
      <Button size="sm" variant="danger" onClick={() => onChange(value.filter((_, i) => i !== index))}>删除</Button>
    </div>)}
  </section>
}
