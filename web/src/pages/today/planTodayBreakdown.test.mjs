import assert from 'node:assert/strict'
import test from 'node:test'
import { planDayDisplay, planTodayBreakdown } from './planTodayBreakdown.mjs'

test('today breakdown separates overdue work from items due today', () => {
  // Derived from RR/RO snapshot 3585858 (catalog 0497b113): 493 overdue + 494 due today.
  assert.deepEqual(planTodayBreakdown({
    start: '2026-10-24',
    day_no: 2,
    today_cards: 460,
    today_questions: 527,
    day_summaries: [{
      no: 1,
      date: '2026-10-25',
      cards: 460,
      questions: 527,
      overdue_cards: 230,
      overdue_questions: 263,
    }],
  }), {
    planDay: 2,
    date: '2026-10-25',
    overdue: 493,
    dueToday: 494,
    total: 987,
  })
})

test('post-replan D2 today summary totals match the live task split', () => {
  assert.deepEqual(planTodayBreakdown({
    start: '2026-10-24',
    day_no: 2,
    today_cards: 256,
    today_questions: 291,
    day_summaries: [{
      no: 1,
      date: '2026-10-25',
      cards: 256,
      questions: 291,
      overdue_cards: 0,
      overdue_questions: 0,
    }],
  }), {
    planDay: 2,
    date: '2026-10-25',
    overdue: 0,
    dueToday: 547,
    total: 547,
  })
})

test('today date is derived from plan start and day number when no daily summary exists', () => {
  assert.deepEqual(planTodayBreakdown({
    start: '2026-10-24',
    day_no: 2,
    today_cards: 0,
    today_questions: 0,
    day_summaries: [],
  }), {
    planDay: 2,
    date: '2026-10-25',
    overdue: 0,
    dueToday: 0,
    total: 0,
  })
})

test('daily rows show plan day, relative date, and calendar date together', () => {
  const plan = { day_no: 2 }
  assert.equal(planDayDisplay(plan, 1, '2026-10-25'), '计划 D2 · 今天 · 2026-10-25')
  assert.equal(planDayDisplay(plan, 2, '2026-10-26'), '计划 D3 · 明天 · 2026-10-26')
})
