import type { QueryClient } from '@tanstack/react-query'

export function invalidateStudy(client: QueryClient) {
  const names = new Set(['plan', 'plan-day', 'today', 'schedule', 'stats-overview', 'related-questions'])
  return client.invalidateQueries({ predicate: (query) => names.has(String(query.queryKey[0])) })
}
