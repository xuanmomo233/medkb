import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/ui'
import s from './chapter.module.css'

const src = (n: number) => `/img/page_${n}.webp`

export default function PageGallery({ pages }: { pages: number[] }) {
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
      <h2 className={s.galleryTitle}>导图原图 <span>共 {pages.length} 页</span></h2>
      <div className={s.grid}>
        {pages.map((n, i) => (
          <button key={n} type="button" className={s.thumb} onClick={() => setCur(i)} aria-label={`查看第 ${n} 页`}>
            <img src={src(n)} alt={`导图第 ${n} 页`} loading="lazy" />
            <span className={s.pageNo}>P{n}</span>
          </button>
        ))}
      </div>
      {cur !== null && createPortal(
        <div className={s.lightbox} onClick={close} role="dialog" aria-modal="true">
          <img src={src(pages[cur])} alt={`导图第 ${pages[cur]} 页`} onClick={(e) => e.stopPropagation()} />
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
