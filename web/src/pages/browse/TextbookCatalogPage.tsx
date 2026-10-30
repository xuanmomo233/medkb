import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { TextbookSource } from '@/api/types'
import { EmptyState, ErrorState, PageHeader, Spinner } from '@/ui'
import s from './textbooks.module.css'

export default function TextbookCatalogPage() {
  const { data, error, refetch } = useQuery({ queryKey: ['textbooks'], queryFn: api.textbooks, staleTime: 60 * 60 * 1000 })
  const groups = useMemo(() => {
    const bySubject = new Map<string, TextbookSource[]>()
    for (const source of data?.sources ?? []) {
      const items = bySubject.get(source.subject) ?? []
      items.push(source)
      bySubject.set(source.subject, items)
    }
    return [...bySubject]
  }, [data])

  return <div>
    <PageHeader title="整本教材" sub="在线翻阅已收录的教材原书；阅读时按需加载页面数据。" />
    {error ? <ErrorState error={error} onRetry={() => void refetch()} />
      : !data ? <Spinner />
        : groups.length === 0 ? <EmptyState text="暂无可阅读的教材" />
          : <div className={s.catalog}>{groups.map(([subject, sources]) => <section key={subject} className={s.group}>
            <h2>{subject}</h2>
            <div className={s.books}>{sources.map((source) => <Link key={source.key} className={s.book} to={`/browse/textbooks/${encodeURIComponent(source.key)}`}>
              <span className={s.bookTitle}>{source.title}</span>
              <span className={s.meta}>{source.publisher} · {source.edition}</span>
              <span className={s.open}>打开教材 <span aria-hidden="true">→</span></span>
            </Link>)}</div>
          </section>)}</div>}
  </div>
}
