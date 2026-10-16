import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, SyntheticEvent } from 'react'
import { api } from '@/api/endpoints'
import { Button, Field, HtmlView, Input, Modal, Spinner } from '@/ui'
import { buildMarkdownTable, highlightSelection, insertTableAtSelection, prefixMarkdownLines, unhighlightSelection, wrapMarkdownSelection } from './markdownEditorHelpers.mjs'
import type { TextEdit, TextSelection } from './markdownEditorHelpers.mjs'
import s from './MarkdownEditor.module.css'

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  kind: 'markdown' | 'card'
}
interface TableDraft { headers: string[]; rows: string[][] }
interface Preview { text: string; kind: Props['kind']; busy: boolean; html?: string; error?: string }
type ResourceKind = 'link' | 'image'
const PREVIEW_LIMIT = 20_000

export default function MarkdownEditor({ label, value, onChange, kind }: Props) {
  const id = useId()
  const textarea = useRef<HTMLTextAreaElement>(null)
  const selection = useRef<TextSelection>({ start: 0, end: 0 })
  const pendingSelection = useRef<TextSelection | null>(null)
  const requestVersion = useRef(0)
  const currentSource = useRef({ text: value, kind })
  const [source, setSource] = useState({ text: value, kind })
  const [message, setMessage] = useState('')
  const [tableOpen, setTableOpen] = useState(false)
  const [table, setTable] = useState<TableDraft>({ headers: ['列 1', '列 2'], rows: [['', ''], ['', '']] })
  const [preview, setPreview] = useState<Preview | null>(null)
  const [resource, setResource] = useState<ResourceKind | null>(null)
  const [resourceText, setResourceText] = useState('')
  const [resourceUrl, setResourceUrl] = useState('')
  const shownPreview = preview?.text === value && preview.kind === kind ? preview : null
  const characterCount = Array.from(value).length
  const overLimit = characterCount > PREVIEW_LIMIT

  if (source.text !== value || source.kind !== kind) {
    setSource({ text: value, kind })
    setPreview(null)
  }
  useLayoutEffect(() => {
    currentSource.current = { text: value, kind }
    requestVersion.current += 1
  }, [value, kind])
  useEffect(() => () => { requestVersion.current += 1 }, [])

  useLayoutEffect(() => {
    const next = pendingSelection.current
    if (next && textarea.current) {
      pendingSelection.current = null
      textarea.current.focus()
      textarea.current.setSelectionRange(next.start, next.end)
      selection.current = next
    }
  }, [value])

  const rememberSelection = (event: SyntheticEvent<HTMLTextAreaElement>) => {
    selection.current = { start: event.currentTarget.selectionStart, end: event.currentTarget.selectionEnd }
  }

  const changeText = (text: string) => {
    // Invalidate synchronously, before React commits the controlled value.
    requestVersion.current += 1
    currentSource.current = { text, kind }
    setPreview(null)
    setMessage('')
    onChange(text)
  }

  const applyEdit = (edit: TextEdit, noChangeMessage: string) => {
    if (!edit.changed) { setMessage(noChangeMessage); return }
    pendingSelection.current = { start: edit.start, end: edit.end }
    changeText(edit.text)
  }

  const highlight = () => {
    const { start, end } = selection.current
    applyEdit(highlightSelection(value, start, end), '请逐段选择要高亮的文字；已高亮的选区不会重复添加。')
  }
  const unhighlight = () => {
    const { start, end } = selection.current
    applyEdit(unhighlightSelection(value, start, end), '请选择完整高亮内容（可包含 == 或 <mark> 标签），不支持局部取消。')
  }
  const inline = (prefix: string, suffix = prefix, placeholder = '文本') => {
    const { start, end } = selection.current
    applyEdit(wrapMarkdownSelection(value, start, end, prefix, suffix, placeholder), '插入位置已失效，请在原文中重新放置光标。')
  }
  const lines = (prefix: string, placeholder = '内容') => {
    const { start, end } = selection.current
    applyEdit(prefixMarkdownLines(value, start, end, prefix, placeholder), '插入位置已失效，请在原文中重新放置光标。')
  }
  const openResource = (next: ResourceKind) => {
    const { start, end } = selection.current
    const selected = value.slice(start, end)
    setResourceText(selected || (next === 'image' ? '图片说明' : '链接文字'))
    setResourceUrl('')
    setResource(next)
  }
  const insertResource = () => {
    if (!resource || !resourceUrl.trim()) return
    const { start, end } = selection.current
    const label = resourceText.trim() || (resource === 'image' ? '图片说明' : '链接文字')
    const prefix = resource === 'image' ? '![' : '['
    applyEdit(wrapMarkdownSelection(value, start, end, prefix, `](${resourceUrl.trim()})`, label, label), '插入位置已失效，请在原文中重新放置光标。')
    setResource(null)
  }

  const addColumn = () => setTable((draft) => draft.headers.length >= 6 ? draft : {
    headers: [...draft.headers, `列 ${draft.headers.length + 1}`], rows: draft.rows.map((row) => [...row, '']),
  })
  const removeColumn = () => setTable((draft) => draft.headers.length <= 2 ? draft : {
    headers: draft.headers.slice(0, -1), rows: draft.rows.map((row) => row.slice(0, -1)),
  })
  const addRow = () => setTable((draft) => draft.rows.length >= 12 ? draft : {
    ...draft, rows: [...draft.rows, draft.headers.map(() => '')],
  })
  const removeRow = () => setTable((draft) => draft.rows.length <= 1 ? draft : { ...draft, rows: draft.rows.slice(0, -1) })

  const insertTable = () => {
    const { start, end } = selection.current
    const edit = insertTableAtSelection(value, start, end, buildMarkdownTable(table.headers, table.rows))
    applyEdit(edit, '插入位置已失效，请在原文中重新放置光标。')
    if (edit.changed) setTableOpen(false)
  }

  const closeTable = () => {
    setTableOpen(false)
    textarea.current?.focus()
  }
  const handleEscape = (event: KeyboardEvent<HTMLDivElement>) => {
    if (tableOpen && event.key === 'Escape') {
      // The outer sheet listens on document: consume Escape before it gets there.
      event.preventDefault()
      event.stopPropagation()
      closeTable()
    }
  }

  const requestPreview = async () => {
    if (overLimit || shownPreview?.busy) return
    const version = ++requestVersion.current
    const source = { text: value, kind }
    const isCurrent = () => version === requestVersion.current
      && currentSource.current.text === source.text && currentSource.current.kind === source.kind
    setPreview({ ...source, busy: true })
    try {
      const response = await api.adminPreview(source)
      if (isCurrent()) setPreview({ ...source, busy: false, html: response.html })
    } catch (error) {
      if (isCurrent()) setPreview({ ...source, busy: false, error: error instanceof Error ? error.message : '预览失败，请重试。' })
    }
  }

  return (
    <div className={s.editor} onKeyDown={handleEscape}>
      <label className={s.label} htmlFor={`${id}-source`}>{label}</label>
      <div className={s.toolbar} role="group" aria-label={`${label}工具`}>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => lines('## ', '二级标题')}>标题</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => inline('**')}>加粗</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => inline('*')}>斜体</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => inline('`', '`', '代码')}>代码</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => lines('> ', '引用内容')}>引用</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => lines('- ', '列表项')}>列表</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => lines('1. ', '列表项')}>编号</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => openResource('link')}>链接</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={() => openResource('image')}>图片</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={highlight}>高亮选区</Button>
        <Button size="sm" onMouseDown={(event) => event.preventDefault()} onClick={unhighlight}>取消高亮</Button>
        <Button size="sm" aria-expanded={tableOpen} aria-controls={`${id}-table`} onClick={() => setTableOpen((open) => !open)}>插入表格</Button>
        <Button size="sm" disabled={overLimit} aria-disabled={Boolean(shownPreview?.busy)} aria-busy={Boolean(shownPreview?.busy)} onClick={requestPreview}>{shownPreview?.busy ? '预览中…' : '预览（不保存）'}</Button>
      </div>
      <textarea id={`${id}-source`} ref={textarea} className={s.source} value={value} rows={10}
        aria-describedby={`${id}-hint`} onSelect={rememberSelection} onBlur={rememberSelection}
        onChange={(event) => { rememberSelection(event); changeText(event.target.value) }} />
      <p className={s.hint} id={`${id}-hint`}>选中文字后可添加 ==高亮==。取消高亮支持完整选中的 ==…== 或 &lt;mark&gt;…&lt;/mark&gt;，也可只选中其全部内容。</p>
      {message && <p className={s.hint} role="status">{message}</p>}
      {tableOpen && (
        <section className={s.builder} id={`${id}-table`} aria-labelledby={`${id}-table-title`}>
          <h3 className={s.builderTitle} id={`${id}-table-title`}>表格编辑</h3>
          <p className={s.hint}>在原文光标（选区起点）处插入，保留选中文字。减列 / 减行会删除最后一列 / 行；取消不会改动原文。</p>
          <div className={s.dimensions}>
            <div className={s.toolbar} role="group" aria-label="表格列数">
              <span>{table.headers.length} 列（2–6）</span>
              <Button size="sm" disabled={table.headers.length <= 2} onClick={removeColumn}>减列</Button>
              <Button size="sm" disabled={table.headers.length >= 6} onClick={addColumn}>加列</Button>
            </div>
            <div className={s.toolbar} role="group" aria-label="表格正文行数">
              <span>{table.rows.length} 行（1–12）</span>
              <Button size="sm" disabled={table.rows.length <= 1} onClick={removeRow}>减行</Button>
              <Button size="sm" disabled={table.rows.length >= 12} onClick={addRow}>加行</Button>
            </div>
          </div>
          <div className={s.tableScroll} role="region" aria-label="表格单元格（可横向滚动）" tabIndex={0}>
            <table className={s.draftTable}>
              <thead><tr>{table.headers.map((header, column) => (
                <th key={column} scope="col"><textarea className={s.cell} rows={2} aria-label={`第 ${column + 1} 列表头`} value={header}
                  onChange={(event) => setTable((draft) => ({ ...draft, headers: draft.headers.map((cell, index) => index === column ? event.target.value : cell) }))} /></th>
              ))}</tr></thead>
              <tbody>{table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>{row.map((cell, column) => (
                  <td key={column}><textarea className={s.cell} rows={2} aria-label={`第 ${rowIndex + 1} 行第 ${column + 1} 列`} value={cell}
                    onChange={(event) => setTable((draft) => ({ ...draft, rows: draft.rows.map((cells, index) => index === rowIndex ? cells.map((entry, cellIndex) => cellIndex === column ? event.target.value : entry) : cells) }))} /></td>
                ))}</tr>
              ))}</tbody>
            </table>
          </div>
          <div className={s.toolbar}>
            <Button size="sm" onClick={closeTable}>取消表格</Button>
            <Button size="sm" variant="primary" onClick={insertTable}>插入到原文</Button>
          </div>
        </section>
      )}
      <p className={overLimit ? s.error : s.hint}>{characterCount.toLocaleString()} / 20,000 字符（仅预览限制）{overLimit && '：请缩短原文后预览。'}</p>
      {shownPreview?.busy && <div role="status" aria-live="polite" aria-busy="true"><span className={s.hint}>正在生成预览…</span><Spinner /></div>}
      {shownPreview?.error && <p className={s.error} role="alert">{shownPreview.error}</p>}
      {shownPreview?.html !== undefined && (
        <section className={s.preview} aria-labelledby={`${id}-preview-title`}>
          <h3 className={s.builderTitle} id={`${id}-preview-title`}>预览（尚未保存）</h3>
          <HtmlView html={shownPreview.html} />
        </section>
      )}
      {resource && (
        <Modal title={resource === 'image' ? '插入图片' : '插入链接'} onClose={() => setResource(null)}>
          <div className={s.resourceForm}>
            <Field label={resource === 'image' ? '图片说明' : '显示文字'}>
              <Input autoFocus value={resourceText} onChange={(event) => setResourceText(event.target.value)} />
            </Field>
            <Field label={resource === 'image' ? '图片地址' : '链接地址'}>
              <Input type="url" placeholder="https://…" value={resourceUrl} onChange={(event) => setResourceUrl(event.target.value)} />
            </Field>
            <div className={s.toolbar}>
              <Button onClick={() => setResource(null)}>取消</Button>
              <Button variant="primary" disabled={!resourceUrl.trim()} onClick={insertResource}>插入</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
