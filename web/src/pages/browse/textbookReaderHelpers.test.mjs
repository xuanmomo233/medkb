import assert from 'node:assert/strict'
import test from 'node:test'
import { errorMessage, textbookPdfUrl } from './textbookReaderHelpers.mjs'

test('textbook PDF URLs encode source keys for the authenticated endpoint', () => {
  assert.equal(textbookPdfUrl('内科学/第10版'), '/api/textbooks/%E5%86%85%E7%A7%91%E5%AD%A6%2F%E7%AC%AC10%E7%89%88.pdf')
})

test('textbook reader reports authorization and missing-asset failures distinctly', () => {
  assert.match(errorMessage(new Error('Unexpected server response (401) while retrieving PDF')), /登录状态无效/)
  assert.match(errorMessage(new Error('Unexpected server response (404) while retrieving PDF')), /尚未上传/)
})
