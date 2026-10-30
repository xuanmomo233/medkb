import assert from 'node:assert/strict'
import test from 'node:test'
import { optionLabels, answerLabels, pickedIndices, optionKey, formatLabeledOptions, parseLabeledOptions, questionOptionPatch } from '../../optionLabels.ts'

const labels = [...'ABCDEFGHJK']
const options = labels.map((label) => `原选项${label}`)

test('non-contiguous ten-option labels preserve J/K and submit array positions', () => {
  assert.deepEqual(optionLabels(10, labels), labels)
  assert.deepEqual(answerLabels('Ａ、Ｊ，Ｋ', labels), ['A', 'J', 'K'])
  assert.deepEqual(pickedIndices('AJK', labels), [0, 8, 9])
  assert.deepEqual(answerLabels('I', labels), null)
  assert.deepEqual(pickedIndices('I', labels), [])
  assert.equal(optionKey('9', labels), 'J')
  assert.equal(optionKey('0', labels), 'K')
  assert.equal(optionKey('j', labels), 'J')
  assert.equal(optionKey('i', labels), undefined)
})

test('old missing/empty metadata supports nine or more continuous options through Z', () => {
  assert.deepEqual(optionLabels(10), [...'ABCDEFGHIJ'])
  assert.deepEqual(optionLabels(10, []), [...'ABCDEFGHIJ'])
  assert.equal(optionLabels(26)[25], 'Z')
  assert.deepEqual(pickedIndices('IZ', optionLabels(26)), [8, 25])
  assert.equal(optionKey('s', optionLabels(26)), 'S')
})

test('malformed explicit labels never silently renumber or accept an unknown answer', () => {
  assert.deepEqual(optionLabels(2, ['A', 'A']), [])
  assert.deepEqual(optionLabels(2, ['A']), [])
  assert.deepEqual(optionLabels(2, ['A', 'j']), [])
  for (const count of [-1, 1.5, 27, NaN]) assert.deepEqual(optionLabels(count), [])
  assert.deepEqual(answerLabels('AJJ', labels), ['A', 'J'])
  assert.equal(answerLabels('A+J', labels), null)
  assert.equal(answerLabels('、AJ', labels), null)
  assert.equal(answerLabels('教材原答案待核实', labels), null)
  assert.equal(answerLabels('', labels), null)
})

test('admin form round trip preserves gaps, empty options and every original label', () => {
  const text = formatLabeledOptions(options, labels)
  assert.match(text, /\nJ\. 原选项J\nK\. 原选项K$/)
  assert.deepEqual(parseLabeledOptions(text), { options, option_labels: labels })
  assert.deepEqual(parseLabeledOptions('A.\nJ. 末项'), { options: ['', '末项'], option_labels: ['A', 'J'] })
  assert.deepEqual(parseLabeledOptions('Ａ． 全角内容Ａ\nＪ）二'), { options: ['全角内容Ａ', '二'], option_labels: ['A', 'J'] })
  assert.deepEqual(parseLabeledOptions(''), { options: [], option_labels: [] })
  assert.throws(() => parseLabeledOptions('A. 一\nA. 二'), /不重复/)
  assert.throws(() => parseLabeledOptions('未带标签'), /保留/)
})

test('unrelated admin edits omit option metadata; label/content edits send matching answer', () => {
  const original = { options, option_labels: labels, answer: 'JK' }
  assert.deepEqual(questionOptionPatch(original, formatLabeledOptions(options, labels), 'JK'), {})
  const next = [...labels.slice(0, 8), 'X', 'Z']
  assert.deepEqual(questionOptionPatch(original, formatLabeledOptions(options, next), 'XZ'), { options, option_labels: next, answer: 'XZ' })
  assert.throws(() => questionOptionPatch(original, formatLabeledOptions(options, next), 'JK'), /现有选项标签/)
  assert.deepEqual(questionOptionPatch({ options: ['一', '二'], answer: 'A' }, 'A. 一\nB. 二', 'A'), {})
  const raw = { options: ['一', '二'], option_labels: ['J', 'K'], answer: 'Ｊ、Ｋ' }
  assert.deepEqual(questionOptionPatch(raw, 'J. 更新一\nK. 二', raw.answer), { options: ['更新一', '二'], option_labels: ['J', 'K'] })
  assert.deepEqual(questionOptionPatch(raw, 'K. 一\nJ. 二', raw.answer), { options: ['一', '二'], option_labels: ['K', 'J'] })
})
