import { useCallback, useEffect, useState } from 'react'

interface Result<T> { fetcher: () => Promise<T>; round: number; data?: T; error?: unknown }

/** 加载异步数据；fetcher 需用 useCallback/useMemo 稳定引用，引用变化即重新加载 */
export function useLoad<T>(fetcher: (() => Promise<T>) | null) {
  const [round, setRound] = useState(0)
  const [res, setRes] = useState<Result<T> | null>(null)

  useEffect(() => {
    if (!fetcher) return
    let alive = true
    fetcher().then(
      (data) => alive && setRes({ fetcher, round, data }),
      (error) => alive && setRes({ fetcher, round, error }),
    )
    return () => { alive = false }
  }, [fetcher, round])

  const cur = fetcher && res && res.fetcher === fetcher && res.round === round ? res : null
  const reload = useCallback(() => setRound((n) => n + 1), [])
  return { data: cur?.data, error: cur?.error, loading: !!fetcher && !cur, reload }
}
