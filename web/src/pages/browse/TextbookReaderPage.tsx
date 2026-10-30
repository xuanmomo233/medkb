import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import type { OnProgressParameters, PDFDocumentLoadingTask, PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { useQuery } from '@tanstack/react-query'
import { tokenStore } from '@/api/client'
import { api } from '@/api/endpoints'
import { ErrorState, Spinner } from '@/ui'
import { errorMessage, textbookPdfUrl } from './textbookReaderHelpers.mjs'
import s from './textbooks.module.css'

GlobalWorkerOptions.workerSrc = workerUrl

interface OutlineEntry { title: string; dest: string | any[] | null; items: OutlineEntry[] }

function OutlineItems({ items, onSelect }: { items: OutlineEntry[]; onSelect: (dest: string | any[]) => void }) {
  return <ul className={s.outlineList}>{items.map((item, index) => <li key={`${item.title}-${index}`}>
    {item.dest ? <button type="button" onClick={() => onSelect(item.dest!)} title={item.title}>{item.title || '未命名书签'}</button> : <span>{item.title}</span>}
    {item.items?.length > 0 && <OutlineItems items={item.items} onSelect={onSelect} />}
  </li>)}</ul>
}

export default function TextbookReaderPage() {
  const { sourceKey = '' } = useParams()
  return <TextbookReader key={sourceKey} sourceKey={sourceKey} />
}

function TextbookReader({ sourceKey }: { sourceKey: string }) {
  const { data: catalog, error: catalogError } = useQuery({ queryKey: ['textbooks'], queryFn: api.textbooks, staleTime: 60 * 60 * 1000 })
  const source = catalog?.sources.find((item) => item.key === sourceKey)
  const hasSource = Boolean(source)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pageWrapRef = useRef<HTMLDivElement>(null)
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [outline, setOutline] = useState<OutlineEntry[] | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [pageInput, setPageInput] = useState('1')
  const [zoom, setZoom] = useState(1)
  const [fitWidth, setFitWidth] = useState(760)
  const [loading, setLoading] = useState(true)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [rendering, setRendering] = useState(false)
  const pdfUrl = useMemo(() => textbookPdfUrl(sourceKey), [sourceKey])

  useEffect(() => {
    if (!hasSource) return
    let active = true
    let task: PDFDocumentLoadingTask | undefined
    task = getDocument({
      url: pdfUrl,
      httpHeaders: tokenStore.get() ? { 'X-Token': tokenStore.get() } : {},
      disableRange: false,
      disableStream: true,
      disableAutoFetch: true,
      rangeChunkSize: 512 * 1024,
    })
    task.onProgress = ({ loaded, total }: OnProgressParameters) => {
      if (!active) return
      setProgress(total > 0 ? Math.min(100, Math.round(loaded / total * 100)) : null)
    }
    task.promise.then(async (document) => {
      const toc = await document.getOutline()
      if (!active) { await task?.destroy(); return }
      setPdf(document); setOutline(toc); setLoading(false)
    }).catch((reason: unknown) => {
      if (!active) return
      setError(errorMessage(reason)); setLoading(false)
    })
    return () => { active = false; void task?.destroy() }
  }, [pdfUrl, hasSource])

  useEffect(() => {
    const element = pageWrapRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setFitWidth(Math.max(280, entry.contentRect.width - 24)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [pdf])

  useEffect(() => {
    if (!pdf || !canvasRef.current) return
    let cancelled = false
    let renderTask: ReturnType<PDFPageProxy['render']> | undefined
    setRendering(true)
    pdf.getPage(pageNumber).then((page) => {
      if (cancelled || !canvasRef.current) return
      const natural = page.getViewport({ scale: 1 })
      const scale = Math.min(2.5, Math.max(0.35, fitWidth / natural.width * zoom))
      const viewport = page.getViewport({ scale })
      const canvas = canvasRef.current
      const context = canvas.getContext('2d', { alpha: false })
      if (!context) throw new Error('浏览器无法创建页面画布')
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.ceil(viewport.width * dpr)
      canvas.height = Math.ceil(viewport.height * dpr)
      canvas.style.width = `${Math.ceil(viewport.width)}px`
      canvas.style.height = `${Math.ceil(viewport.height)}px`
      renderTask = page.render({ canvas, canvasContext: context, viewport, transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0], background: 'white' })
      return renderTask.promise
    }).catch((reason: unknown) => {
      if (!cancelled && !(reason instanceof Error && reason.name === 'RenderingCancelledException')) setError(errorMessage(reason))
    }).finally(() => { if (!cancelled) setRendering(false) })
    return () => { cancelled = true; renderTask?.cancel() }
  }, [pdf, pageNumber, zoom, fitWidth])

  const goPage = (value: number) => {
    if (!pdf) return
    const next = Math.max(1, Math.min(pdf.numPages, Math.trunc(value)))
    setPageNumber(next); setPageInput(String(next))
  }
  const selectDestination = async (destination: string | any[]) => {
    if (!pdf) return
    try {
      const dest = typeof destination === 'string' ? await pdf.getDestination(destination) : destination
      if (!dest?.[0]) return
      const index = await pdf.getPageIndex(dest[0] as Parameters<PDFDocumentProxy['getPageIndex']>[0])
      goPage(index + 1)
    } catch { /* 有缺陷的书签不应阻断阅读 */ }
  }

  if (!catalog && !catalogError) return <Spinner />
  if (!catalog && catalogError) return <ErrorState error={catalogError} onRetry={() => window.location.reload()} />
  if (!source) return <div><ErrorState error={new Error('目录中找不到这本教材。')} onRetry={() => window.location.assign('/browse/textbooks')} /><Link to="/browse/textbooks">返回教材目录</Link></div>

  return <div className={s.reader}>
    <header className={s.readerHeader}>
      <div className={s.readerTitle}><Link to="/browse/textbooks">教材目录</Link><span aria-hidden="true">/</span><h1>{source.title}</h1><span className={s.readerMeta}>{source.publisher} · {source.edition}</span></div>
      <div className={s.readerTools}>
        <button type="button" onClick={() => setZoom((z) => Math.max(.5, Math.round((z - .1) * 10) / 10))} aria-label="缩小">−</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom((z) => Math.min(2.5, Math.round((z + .1) * 10) / 10))} aria-label="放大">＋</button>
        <button type="button" onClick={() => setZoom(1)}>适合宽度</button>
        <span className={s.divider} />
        <button type="button" onClick={() => goPage(pageNumber - 1)} disabled={!pdf || pageNumber <= 1}>上一页</button>
        <form className={s.pageJump} onSubmit={(event) => { event.preventDefault(); goPage(Number(pageInput) || 1) }}>
          <input inputMode="numeric" aria-label="跳转到页码" value={pageInput} onChange={(event) => setPageInput(event.target.value.replace(/[^\d]/g, ''))} />
          <span>/ {pdf?.numPages ?? '—'}</span><button type="submit" disabled={!pdf}>跳转</button>
        </form>
        <button type="button" onClick={() => goPage(pageNumber + 1)} disabled={!pdf || pageNumber >= pdf.numPages}>下一页</button>
      </div>
    </header>
    {error && <div className={s.readerError} role="alert"><p>{error}</p>{/登录/.test(error) && <Link to="/login">前往登录</Link>}<button type="button" onClick={() => window.location.reload()}>重试</button></div>}
    {loading && <div className={s.loadStatus} role="status"><Spinner /><span>正在加载教材…{progress == null ? '' : ` ${progress}%`}</span>{progress != null && <progress max={100} value={progress} />}</div>}
    <div className={s.readerLayout}>
      {outline && outline.length > 0 && <aside className={s.outline} aria-label="教材书签目录"><h2>书签目录</h2><OutlineItems items={outline} onSelect={(dest) => void selectDestination(dest)} /></aside>}
      <section className={s.pageArea} ref={pageWrapRef} aria-label="教材页面">
        {!loading && !error && !pdf ? <p>正在打开教材…</p> : null}
        {pdf && <div className={s.pagePaper} aria-busy={rendering}><canvas ref={canvasRef} aria-label={`${source.title}第${pageNumber}页`} />{rendering && <span className={s.renderStatus}>正在绘制页面…</span>}</div>}
      </section>
    </div>
  </div>
}
