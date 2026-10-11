import { useEffect, useState } from 'react'

export function useAsync<T>(fn: () => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: unknown }>({})
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let off = false
    fn().then(
      (data) => { if (!off) setState({ data }) },
      (error: unknown) => { if (!off) setState({ error }) },
    )
    return () => { off = true }
  }, [fn, attempt])

  return { ...state, retry: () => { setState({}); setAttempt((n) => n + 1) } }
}
