import test from 'node:test'
import assert from 'node:assert/strict'
import { buildMarkdownTable, escapeTableCell, highlightSelection, insertTableAtSelection, normalizeSelection, unhighlightSelection } from './markdownEditorHelpers.mjs'

test('highlight preserves Unicode, outside text, and the selected caret range', () => {
  const text = '前😀重点e\u0301后'
  const edit = highlightSelection(text, 1, text.length - 1)
  assert.equal(edit.text, '前==😀重点e\u0301==后')
  assert.equal(edit.text.slice(edit.start, edit.end), '😀重点e\u0301')
  assert.deepEqual(unhighlightSelection(edit.text, edit.start, edit.end), {
    text, start: 1, end: text.length - 1, changed: true,
  })
})

test('reversed and partial surrogate selections are normalized without corrupting text', () => {
  assert.deepEqual(normalizeSelection('a😀b', 3, 1), { start: 1, end: 3 })
  assert.equal(highlightSelection('a😀b', 2, 3).text, 'a==😀==b')
  assert.deepEqual(normalizeSelection('a😀b', 2, 2), { start: 3, end: 3 })
})

test('invalid, empty, and already highlighted selections are safe no-ops', () => {
  for (const [start, end] of [[-1, 1], [0, 9], [NaN, 1], [0.5, 2], [1, 1]]) {
    assert.equal(highlightSelection('abc', start, end).text, 'abc')
    assert.equal(unhighlightSelection('abc', start, end).changed, false)
  }
  assert.equal(highlightSelection('==重点==', 2, 4).changed, false)
  assert.equal(highlightSelection('==重点==', 0, 6).changed, false)
  assert.equal(unhighlightSelection('==重点==', 2, 3).changed, false)
  assert.equal(unhighlightSelection('plain', 0, 5).changed, false)
})

test('unhighlight supports selected complete Markdown and legacy mark wrappers', () => {
  const selected = '==甲== 与 <mark class="manual">乙😀</mark> 和 <mark>丙</mark>'
  const text = `前${selected}后`
  const edit = unhighlightSelection(text, 1, text.length - 1)
  assert.equal(edit.text, '前甲 与 乙😀 和 丙后')
  assert.equal(edit.text.slice(edit.start, edit.end), '甲 与 乙😀 和 丙')
  const legacy = '前<mark class="manual">重点😀</mark>后'
  const start = legacy.indexOf('重点')
  const end = legacy.indexOf('</mark>')
  assert.deepEqual(unhighlightSelection(legacy, start, end), { text: '前重点😀后', start: 1, end: 5, changed: true })
})

test('highlighting is safe for partial wrappers, whitespace and paragraphs', () => {
  assert.equal(highlightSelection('==abcdef==', 3, 5).changed, false)
  assert.equal(highlightSelection('<mark>abcdef</mark>', 8, 10).changed, false)
  assert.equal(highlightSelection('  ', 0, 2).changed, false)
  assert.equal(highlightSelection('甲\n\n乙', 0, 4).changed, false)
  assert.equal(highlightSelection('前 word 后', 1, 7).text, '前== word ==后')
})

test('clipped wrappers cannot merge distinct highlights or damage escapes', () => {
  assert.equal(unhighlightSelection('==one== and ==two==', 5, 14).changed, false)
  assert.equal(unhighlightSelection('==one== and ==two==', 2, 16).changed, false)
  assert.equal(unhighlightSelection('\\==literal==', 3, 10).changed, false)
  const text = '==one== and ==two=='
  assert.equal(unhighlightSelection(text, 0, text.length).text, 'one and two')
})

test('table escaping preserves literal pipes, backslashes, HTML characters, and all newline forms', () => {
  assert.equal(escapeTableCell('A|B\\|C\r\nD\nE\rF & <b>'), 'A&#124;B\\\\&#124;C<br>D<br>E<br>F &amp; &lt;b&gt;')
  const table = buildMarkdownTable(['列|一', '列二'], [['a\nb', 'c|d']])
  assert.equal(table, '| 列&#124;一 | 列二 |\n| --- | --- |\n| a<br>b | c&#124;d |')
  assert.equal(table.split('\n').length, 3)
})

test('table dimension limits include both minimum and maximum', () => {
  assert.equal(buildMarkdownTable(['a', 'b'], [['', '']]).split('\n').length, 3)
  assert.equal(buildMarkdownTable(Array(6).fill('h'), Array.from({ length: 12 }, () => Array(6).fill('c'))).split('\n').length, 14)
  for (const [columns, rows] of [[1, 1], [7, 1], [2, 0], [2, 13]]) {
    assert.throws(() => buildMarkdownTable(Array(columns).fill(''), Array.from({ length: rows }, () => [])), RangeError)
  }
})

test('table insertion never replaces selected content and returns the insertion caret', () => {
  const table = buildMarkdownTable(['h1', 'h2'], [['a', 'b']])
  const text = '前选中😀后'
  const edit = insertTableAtSelection(text, 1, 5, table)
  assert.equal(edit.text, `前\n\n${table}\n\n选中😀后`)
  assert.equal(edit.text.slice(edit.start), '选中😀后')
  assert.equal(edit.start, edit.end)
  assert.equal(insertTableAtSelection(text, 5, 1, table).text, edit.text)
  assert.equal(insertTableAtSelection(text, -1, 2, table).changed, false)
})

test('table insertion respects beginning/end, existing blank lines, and Unicode caret boundaries', () => {
  assert.equal(insertTableAtSelection('', 0, 0, 'table').text, 'table\n')
  assert.equal(insertTableAtSelection('a\n\nb', 3, 3, 'table').text, 'a\n\ntable\n\nb')
  assert.equal(insertTableAtSelection('a', 1, 1, 'table').text, 'a\n\ntable\n')
  assert.equal(insertTableAtSelection('😀a', 1, 1, 'table').text, '😀\n\ntable\n\na')
  assert.equal(insertTableAtSelection('a', 0, 0, '').changed, false)
})
