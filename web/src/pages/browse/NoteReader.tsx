import { useEffect, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { Card, HtmlView } from '@/ui'
import s from './chapter.module.css'

interface Heading {
  id: string
  title: string
  element: HTMLElement
  children: Heading[]
}

/** Read only the DOM already sanitized by HtmlView; never parse/inject source HTML here. */
export default function NoteReader({ html, chapterId }: { html: string; chapterId: number }) {
  const body = useRef<HTMLDivElement>(null)
  const [sections, setSections] = useState<Heading[]>([])

  useEffect(() => {
    const root = body.current
    if (!root) return
    const outline: Heading[] = []
    const restore: (() => void)[] = []
    let parent: Heading | null = null

    root.querySelectorAll<HTMLElement>('h2, h3').forEach((element, index) => {
      const id = `note-${chapterId}-section-${index + 1}`
      const oldId = element.getAttribute('id')
      const oldTabIndex = element.getAttribute('tabindex')
      element.id = id
      element.tabIndex = -1
      restore.push(() => {
        if (oldId === null) element.removeAttribute('id')
        else element.id = oldId
        if (oldTabIndex === null) element.removeAttribute('tabindex')
        else element.setAttribute('tabindex', oldTabIndex)
      })
      const heading: Heading = {
        id,
        title: element.textContent?.trim() || `未命名小节 ${index + 1}`,
        element,
        children: [],
      }
      if (element.tagName === 'H3' && parent) parent.children.push(heading)
      else outline.push(heading)
      if (element.tagName === 'H2') parent = heading
    })

    // Wrap rendered tables, not their HTML strings, retaining native table semantics.
    root.querySelectorAll<HTMLTableElement>('table').forEach((table, index) => {
      const scroll = document.createElement('div')
      scroll.className = s.tableScroll
      scroll.tabIndex = 0
      scroll.setAttribute('role', 'region')
      scroll.setAttribute('aria-label', `表格 ${index + 1}，可横向滚动`)
      table.before(scroll)
      scroll.append(table)
      restore.push(() => { scroll.replaceWith(table) })
    })
    setSections(outline)

    // Deterministic ordinal IDs also allow direct links to repeated headings.
    const target = document.getElementById(window.location.hash.slice(1))
    if (target && root.contains(target)) target.scrollIntoView({ block: 'start' })
    return () => { restore.reverse().forEach((undo) => undo()) }
  }, [html, chapterId])

  const jump = (event: MouseEvent<HTMLAnchorElement>, heading: Heading) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    heading.element.scrollIntoView({
      block: 'start',
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })
    heading.element.focus({ preventScroll: true })
    window.history.replaceState(window.history.state, '', `#${heading.id}`)
  }

  const link = (heading: Heading) => (
    <a href={`#${heading.id}`} onClick={(event) => jump(event, heading)}>{heading.title}</a>
  )

  return (
    <>
      {sections.length > 0 && (
        <nav className={s.toc} aria-label="本章小节">
          <details open>
            <summary>本章目录 <span>{sections.reduce((count, heading) => count + 1 + heading.children.length, 0)} 个小节</span></summary>
            <ol>
              {sections.map((heading) => (
                <li key={heading.id}>
                  {link(heading)}
                  {heading.children.length > 0 && (
                    <ol>{heading.children.map((child) => <li key={child.id}>{link(child)}</li>)}</ol>
                  )}
                </li>
              ))}
            </ol>
          </details>
        </nav>
      )}
      <Card className={`${s.body} ${s.noteBody}`}>
        <div ref={body}><HtmlView html={html} className={s.noteRich} /></div>
      </Card>
    </>
  )
}
