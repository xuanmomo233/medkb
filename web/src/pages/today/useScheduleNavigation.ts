import { useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useAuth } from '@/app/auth'
import { keys } from './queries'
import { scheduleIndex, schedulePath } from './schedulePath'

export function useScheduleNavigation(enabled = true) {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const id = Number(params.get('schedule_item'))
  const active = enabled && id > 0
  const query = useQuery({ queryKey: keys.schedule, queryFn: api.scheduleToday, enabled: active })
  const items = query.data?.items ?? []
  const index = scheduleIndex(items, id)
  const mode = params.get('mode')
  const go = useCallback((next: number) => {
    if (next < 0 || next >= items.length || next === index) return
    const path = schedulePath(items[next])
    nav(mode === 'quick' || mode === 'recite' ? `${path}&mode=${mode}` : path, { replace: true })
  }, [items, index, mode, nav])
  const next = useCallback(() => go(index + 1), [go, index])
  return {
    active, items, index, total: items.length, go, next,
    pending: active && query.isPending,
    error: active ? query.error : null,
    reload: () => { void query.refetch() },
    scope: !active ? undefined : query.data && index >= 0 ? `${user?.id}:${query.data.day}` : null,
  }
}

export type ScheduleNavigationState = ReturnType<typeof useScheduleNavigation>
