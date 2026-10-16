// Textarea offsets are UTF-16 offsets. Never split a surrogate pair.
export function normalizeSelection(text, start, end) {
  if (!Number.isInteger(start) || !Number.isInteger(end)
    || start < 0 || end < 0 || start > text.length || end > text.length) return null
  if (start > end) [start, end] = [end, start]
  const splitsPair = (offset) => offset > 0 && offset < text.length
    && /[\uD800-\uDBFF]/.test(text[offset - 1]) && /[\uDC00-\uDFFF]/.test(text[offset])
  if (start === end) {
    if (splitsPair(start)) start = end = start + 1
  } else {
    if (splitsPair(start)) start -= 1
    if (splitsPair(end)) end += 1
  }
  return { start, end }
}

function unchanged(text, selection) {
  return { text, start: selection?.start ?? text.length, end: selection?.end ?? text.length, changed: false }
}

function replaceRange(text, from, to, replacement, start, end) {
  return { text: text.slice(0, from) + replacement + text.slice(to), start, end, changed: true }
}

function highlightSpans(text) {
  const escaped = (offset) => {
    let slashes = 0
    for (let i = offset - 1; i >= 0 && text[i] === '\\'; i--) slashes++
    return slashes % 2 === 1
  }
  const spans = []
  for (const match of text.matchAll(/(?<![=])==((?:(?!==).)+?)==(?![=])|<mark\b[^>]*>([\s\S]*?)<\/mark\s*>/gis)) {
    const from = match.index
    const to = from + match[0].length
    const openLength = match[1] === undefined ? match[0].indexOf('>') + 1 : 2
    const closeLength = match[1] === undefined ? match[0].match(/<\/mark\s*>$/i)[0].length : 2
    if (match[1] !== undefined && (escaped(from) || escaped(to - 2))) continue
    spans.push({ from, to, openLength, closeLength })
  }
  return spans
}

export function highlightSelection(text, start, end) {
  const selection = normalizeSelection(text, start, end)
  if (!selection || selection.start === selection.end) return unchanged(text, selection)
  const selected = text.slice(selection.start, selection.end)
  if (!selected.trim() || selected.includes('==') || /\n[ \t]*\r?\n/.test(selected)
    || highlightSpans(text).some((span) => selection.start < span.to && selection.end > span.from)) {
    return unchanged(text, selection)
  }
  return replaceRange(text, selection.start, selection.end, `==${selected}==`, selection.start + 2, selection.end + 2)
}

// Remove real pairs only: never treat two clipped wrappers as a new pair.
export function unhighlightSelection(text, start, end) {
  const selection = normalizeSelection(text, start, end)
  if (!selection || selection.start === selection.end) return unchanged(text, selection)
  const { start: from, end: to } = selection
  const spans = highlightSpans(text)
  const applicable = spans.filter((span) =>
    (from <= span.from && to >= span.to)
    || (from === span.from + span.openLength && to === span.to - span.closeLength))
  if (!applicable.length) return unchanged(text, selection)
  if (spans.some((span) => from < span.to && to > span.from && !applicable.includes(span))) {
    return unchanged(text, selection)
  }
  const removed = applicable.flatMap((span) => [
    [span.from, span.from + span.openLength], [span.to - span.closeLength, span.to],
  ])
  let plain = ''
  let previous = 0
  for (const [a, b] of removed) { plain += text.slice(previous, a); previous = b }
  plain += text.slice(previous)
  const mapped = (offset) => offset - removed.reduce((count, [a, b]) => count + Math.max(0, Math.min(offset, b) - a), 0)
  return { text: plain, start: mapped(from), end: mapped(to), changed: true }
}

export function wrapMarkdownSelection(text, start, end, prefix, suffix = prefix, placeholder = '文本', content) {
  const selection = normalizeSelection(text, start, end)
  if (!selection || !prefix) return unchanged(text, selection)
  const selected = text.slice(selection.start, selection.end)
  const inner = (content ?? selected) || placeholder
  return replaceRange(text, selection.start, selection.end, `${prefix}${inner}${suffix}`,
    selection.start + prefix.length, selection.start + prefix.length + inner.length)
}

export function prefixMarkdownLines(text, start, end, prefix, placeholder = '内容') {
  const selection = normalizeSelection(text, start, end)
  if (!selection || !prefix) return unchanged(text, selection)
  const lineStart = text.lastIndexOf('\n', Math.max(0, selection.start - 1)) + 1
  const nextBreak = text.indexOf('\n', selection.end)
  const lineEnd = nextBreak === -1 ? text.length : nextBreak
  const source = text.slice(lineStart, lineEnd) || placeholder
  const rewritten = source.split('\n').map((line) => `${prefix}${line || placeholder}`).join('\n')
  return replaceRange(text, lineStart, lineEnd, rewritten, lineStart, lineStart + rewritten.length)
}

export function escapeTableCell(value) {
  // Entities avoid even/odd backslash problems before literal pipes in tables.
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\\/g, '\\\\').replace(/\|/g, '&#124;').replace(/\r\n|\r|\n/g, '<br>')
}

export function buildMarkdownTable(headers, rows) {
  if (headers.length < 2 || headers.length > 6 || rows.length < 1 || rows.length > 12) {
    throw new RangeError('Tables require 2–6 columns and 1–12 body rows')
  }
  const line = (cells) => `| ${headers.map((_, column) => escapeTableCell(cells[column] ?? '')).join(' | ')} |`
  return [line(headers), `| ${headers.map(() => '---').join(' | ')} |`, ...rows.map(line)].join('\n')
}

export function insertTableAtSelection(text, start, end, table) {
  const selection = normalizeSelection(text, start, end)
  if (!selection || !table) return unchanged(text, selection)
  // Insert before the selection, never replace it. Blank lines keep the table
  // separate from adjacent Markdown, including insertion in the middle of text.
  const at = selection.start
  const before = text.slice(0, at)
  const after = text.slice(at)
  const prefix = before ? (before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n') : ''
  const suffix = after ? (after.startsWith('\n\n') ? '' : after.startsWith('\n') ? '\n' : '\n\n') : '\n'
  const insertion = prefix + table + suffix
  const caret = at + insertion.length
  return replaceRange(text, at, at, insertion, caret, caret)
}
