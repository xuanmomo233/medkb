import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { getBlob } from '@/api/client'
import { Button } from '@/ui'
import s from './chapter.module.css'

const guideSrc = (n: number) => `/img/page_${String(n).padStart(3, '0')}.webp`

function GalleryImage({ page, sourceKey, alt }: { page: number; sourceKey?: string; alt: string }) {
  const [url, setUrl] = useState(sourceKey ? '' : guideSrc(page))
  useEffect(() => {
    if (!sourceKey) {
      setUrl(guideSrc(page))
      return
    }
    let objectUrl = ''
    let cancelled = false
    setUrl('')
    getBlob(`/textbook-images/${encodeURIComponent(sourceKey)}/${page}.webp`)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (!cancelled) setUrl(objectUrl)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [page, sourceKey])
  return url ? <img src={url} alt={alt} loading="lazy" /> : <span className={s.imageLoading}>图片加载中…</span>
}

export default function PageGallery({ pages, title = '导图原图', sourceKey }: { pages: number[]; title?: string; sourceKey?: string }) {
  const [cur, setCur] = useState<number | null>(null)
  const close = useCallback(() => setCur(null), [])
  const step = useCallback((d: number) => setCur((c) => (c === null ? c : Math.min(pages.length - 1, Math.max(0, c + d)))), [pages.length])

  useEffect(() => {
    if (cur === null) return
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
      else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === 'ArrowRight') step(1)
    }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [cur, close, step])

  return (
    <section className={s.gallery}>
      <h2 className={s.galleryTitle}>{title} <span>共 {pages.length} 页</span></h2>
      <div className={s.grid}>
        {pages.map((n, i) => (
          <button key={n} type="button" className={s.thumb} onClick={() => setCur(i)} aria-label={`查看第 ${n} 页`}>
            <GalleryImage page={n} sourceKey={sourceKey} alt={`${title}第 ${n} 页`} />
            <span className={s.pageNo}>P{n}</span>
          </button>
        ))}
      </div>
      {cur !== null && createPortal(
        <div className={s.lightbox} onClick={close} role="dialog" aria-modal="true">
          <div className={s.lightboxImage} onClick={(e) => e.stopPropagation()}>
            <GalleryImage page={pages[cur]} sourceKey={sourceKey} alt={`${title}第 ${pages[cur]} 页`} />
          </div>
          <div className={s.lbBar} onClick={(e) => e.stopPropagation()}>
            <Button size="sm" disabled={cur === 0} onClick={() => step(-1)}>上一页</Button>
            <span>{cur + 1} / {pages.length}</span>
            <Button size="sm" disabled={cur === pages.length - 1} onClick={() => step(1)}>下一页</Button>
            <Button size="sm" variant="danger" onClick={close}>关闭</Button>
          </div>
        </div>, document.body)}
    </section>
  )
}
