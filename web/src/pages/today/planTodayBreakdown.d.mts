import type { PlanToday } from '../../api/types'

export interface PlanTodayBreakdown {
  planDay: number
  date: string
  overdue: number
  dueToday: number
  total: number
}

export function planTodayBreakdown(plan: PlanToday): PlanTodayBreakdown
export function planDayDisplay(plan: Pick<PlanToday, 'day_no'>, relativeDay: number, date: string): string
