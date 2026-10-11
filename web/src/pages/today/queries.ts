import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/endpoints'

export const keys = {
  today: ['today'] as const,
  calendar: ['calendar'] as const,
  schedule: ['schedule'] as const,
  plan: ['plan'] as const,
}

export const useTodayQuery = () => useQuery({ queryKey: keys.today, queryFn: api.today })
export const useStatsQuery = () => useQuery({ queryKey: ['stats-overview'], queryFn: api.statsOverview })
