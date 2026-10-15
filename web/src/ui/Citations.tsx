import type { ContentCitation } from '@/api/types'
import s from './Citations.module.css'

const statusText = { verified: '已按教材核验', unverified: '待核验', disputed: '存在争议' }

function pages(citation: ContentCitation) {
  if (citation.page_start == null) return ''
  const end = citation.page_end ?? citation.page_start
  return end === citation.page_start ? `第 ${citation.page_start} 页` : `第 ${citation.page_start}-${end} 页`
}

export default function Citations({ items = [] }: { items?: ContentCitation[] }) {
  if (!items.length) return null
  return <section className={s.box} aria-label="教材出处">
    <h3 className={s.title}>教材出处</h3>
    <ul className={s.list}>{items.map((citation) => {
      const location = [citation.chapter, citation.section, pages(citation)].filter(Boolean).join(' · ')
      return <li key={citation.id}>
        {citation.publisher}《{citation.title}》{citation.edition}{location && ` · ${location}`}
        <span className={`${s.status} ${s[citation.status]}`}>{statusText[citation.status]}</span>
        {citation.note && <div className={s.note}>{citation.note}</div>}
      </li>
    })}</ul>
  </section>
}
