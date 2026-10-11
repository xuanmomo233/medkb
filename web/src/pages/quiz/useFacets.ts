import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/endpoints'
import type { FacetProgress, QuizFilter } from '@/api/types'
import { FACET_LEVELS } from './lib'

export function useFacets() {
  const [filter, setFilter] = useState<QuizFilter>({})
  const [facets, setFacets] = useState<FacetProgress | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const seq = useRef(0)

  const fetchFacets = useCallback((f: QuizFilter) => {
    const n = ++seq.current
    api.facets(f).then(
      (r) => { if (n === seq.current) { setFacets(r); setLoading(false) } },
      (e: unknown) => { if (n === seq.current) { setError(e); setLoading(false) } },
    )
  }, [])

  const load = useCallback((f: QuizFilter) => {
    setLoading(true)
    setError(null)
    fetchFacets(f)
  }, [fetchFacets])

  useEffect(() => { fetchFacets({}) }, [fetchFacets])

  const choose = useCallback((level: keyof QuizFilter, value: string) => {
    const idx = FACET_LEVELS.findIndex((l) => l.key === level)
    const next: QuizFilter = {}
    for (const l of FACET_LEVELS.slice(0, idx)) if (filter[l.key]) next[l.key] = filter[l.key]
    if (value) next[level] = value
    setFilter(next)
    load(next)
  }, [filter, load])

  const reset = useCallback(() => { setFilter({}); load({}) }, [load])

  return { filter, facets, loading, error, choose, reset, retry: () => load(filter) }
}
