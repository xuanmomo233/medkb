import DOMPurify from 'dompurify'
import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'

const ALLOWED_CLASS = new Set(['ex', 'yr', 'kw', 'sec', 'tag'])

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.hasAttribute('class')) {
    const keep = node.getAttribute('class')!.split(/\s+/).filter((c) => ALLOWED_CLASS.has(c))
    if (keep.length) node.setAttribute('class', keep.join(' '))
    else node.removeAttribute('class')
  }
})

export function sanitize(html: string): string {
  return DOMPurify.sanitize(html || '', {
    ALLOWED_TAGS: ['p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'em', 'strong', 'b', 'i', 'u', 's', 'del', 'ins', 'mark', 'span', 'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sup', 'sub', 'small', 'div', 'details', 'summary'],
    ALLOWED_ATTR: ['href', 'title', 'class', 'src', 'alt', 'loading', 'colspan', 'rowspan', 'open'],
    ALLOWED_URI_REGEXP: /^(?:\/|https?:|data:image\/|#|mailto:)/i,
  })
}

/** 渲染服务端 HTML：二次消毒 + 统一排版（.rich）+ 点击图片放大 */
export default function HtmlView({ html, className }: { html: string; className?: string }) {
  const clean = useMemo(() => sanitize(html), [html])
  const [zoom, setZoom] = useState<string | null>(null)
  return (
    <>
      <div
        className={`rich ${className ?? ''}`}
        dangerouslySetInnerHTML={{ __html: clean }}
        onClick={(e) => { const t = e.target as HTMLElement; if (t.tagName === 'IMG') setZoom((t as HTMLImageElement).src) }}
      />
      {zoom && createPortal(
        <div onClick={() => setZoom(null)} style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'rgb(0 0 0 / 82%)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'zoom-out', padding: 16 }}>
          <img src={zoom} alt="" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
        </div>, document.body)}
    </>
  )
}
