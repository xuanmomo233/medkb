function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function planDate(start, dayNo) {
  if (typeof start !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(start)) return ''
  const [year, month, day] = start.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day + Math.max(0, dayNo - 1)))
  return date.toISOString().slice(0, 10)
}

export function planTodayBreakdown(plan) {
  const dayNo = number(plan.day_no)
  const today = Array.isArray(plan.day_summaries)
    ? plan.day_summaries.find((summary) => summary.no === 1)
    : undefined
  const cards = number(plan.today_cards)
  const questions = number(plan.today_questions)
  const overdueCards = number(today?.overdue_cards)
  const overdueQuestions = number(today?.overdue_questions)

  return {
    planDay: dayNo,
    date: today?.date || planDate(plan.start, dayNo),
    overdue: overdueCards + overdueQuestions,
    dueToday: Math.max(0, cards - overdueCards) + Math.max(0, questions - overdueQuestions),
    total: cards + questions,
  }
}

export function planDayDisplay(plan, relativeDay, date) {
  const dayNo = number(plan.day_no) + Math.max(1, number(relativeDay)) - 1
  const relative = relativeDay === 1 ? '今天'
    : relativeDay === 2 ? '明天'
      : relativeDay === 3 ? '后天' : '后续'
  return `计划 D${dayNo} · ${relative} · ${date}`
}
