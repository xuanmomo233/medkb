import { useCallback, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { Badge, Card, ErrorState, HtmlView, Spinner } from '@/ui'
import PageGallery from './PageGallery'
import { useLoad } from './useLoad'
import s from './chapter.module.css'

export default function ChapterPage() {
  const { id } = useParams()
  const fetcher = useCallback(() => api.chapter(Number(id)), [id])
  const { data, error, reload } = useLoad(fetcher)

  useEffect(() => { window.scrollTo(0, 0) }, [id])

  const metas = data ? Object.entries(data.meta).filter(([, v]) => v) : []

  return (
    <div className={s.wrap}>
      <Link to="/browse" className={s.back}>‹ 返回目录</Link>
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
            <Card className={s.body}><HtmlView html={data.html} /></Card>
            {data.pages.length > 0 && <PageGallery pages={data.pages} />}
          </>
        )}
    </div>
  )
}
