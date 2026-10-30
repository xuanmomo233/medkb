import assert from 'node:assert/strict'
import test from 'node:test'
import { scheduleIndex, schedulePath } from './schedulePath.ts'

const items = [
  { id: 10, source_ids: [10], item_type: 'card', item_id: 5, done: true },
  { id: 20, source_ids: [20, 22, 25], item_type: 'question', item_id: 100, done: true },
  { id: 30, source_ids: [30], item_type: 'question', item_id: 200, done: false },
]

test('merged historical schedule row keeps position and next unfinished navigation', () => {
  const index = scheduleIndex(items, 25)
  assert.equal(index, 1)
  assert.equal(items[index].done, true)
  const next = items.slice(index + 1).find((item) => !item.done)
  assert.equal(schedulePath(next), '/quiz/run?ids=200&schedule_item=30')
  assert.equal(schedulePath(items[index - 1]), '/cards/run?ids=5&schedule_item=10')
})

test('canonical row IDs and old backend responses remain compatible', () => {
  assert.equal(scheduleIndex(items, 20), 1)
  assert.equal(scheduleIndex([{ id: 22 }], 22), 0)
  assert.equal(scheduleIndex([{ id: 22, source_ids: [] }], 22), 0)
  assert.equal(scheduleIndex(items, 999), -1)
  assert.equal(scheduleIndex([], 25), -1)
})
