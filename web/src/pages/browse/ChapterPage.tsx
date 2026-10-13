import { useCallback, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Badge, Card, ErrorState, HtmlView, Icon, Spinner } from '@/ui'
import PageGallery from './PageGallery'
import NoteReader from './NoteReader'
import { useLoad } from './useLoad'
import s from './chapter.module.css'

const fetchTree = () => api.tree()

export default function ChapterPage() {
  const { id } = useParams()
  const fetcher = useCallback(() => api.chapter(Number(id)), [id])
  const { data, error, reload } = useLoad(fetcher)
  const { data: tree } = useLoad(fetchTree)
  // ChapterDetail has no kind; use authoritative note IDs rather than title/page heuristics.
  const isNote = !!data && !!tree?.notes.some((note) => note.id === data.id)

  useEffect(() => { window.scrollTo(0, 0) }, [id])

  const metas = data ? Object.entries(data.meta).filter(([, v]) => v) : []

  return (
    <div className={`${s.wrap} ${isNote ? s.noteWrap : ''}`}>
      <Link to="/browse" className={s.back}><Icon name="chevLeft" size={14} /> 返回目录</Link>
      {error ? <ErrorState error={error} onRetry={reload} />
        : !data ? <Spinner />
        : (
          <>
            <header className={s.head}>
              <h1 className={s.title}>{data.title}</h1>
              <div className={s.badges}><Badge tone="brand">{data.subject}</Badge></div>
              {metas.length > 0 && (
                <dl className={s.meta}>
                  {metas.map(([k, v]) => (
                    <div key={k} className={s.metaItem}><dt>{k}</dt><dd>{v}</dd></div>
                  ))}
                </dl>
              )}
            </header>
            {isNote
              ? <NoteReader key={data.id} chapterId={data.id} html={data.html} />
              : <Card className={s.body}><HtmlView html={data.html} /></Card>}
            {data.pages.length > 0 && <PageGallery pages={data.pages} />}
          </>
        )}
    </div>
  )
}
