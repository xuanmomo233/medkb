import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { ErrorState } from '@/ui'
import s from './today.module.css'

export function Skeleton({ height = 96 }: { height?: number }) {
  return <div className={s.skeleton} style={{ height }} aria-busy="true" aria-label="加载中" />
}

export function Async<T>({ q, height, children }: { q: UseQueryResult<T>; height?: number; children: (data: T) => ReactNode }) {
  if (q.isPending) return <Skeleton height={height} />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />
  return <>{children(q.data)}</>
}
