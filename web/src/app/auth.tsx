import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import { setUnauthorizedHandler, tokenStore } from '@/api/client'
import type { AuthResult, User } from '@/api/types'
import { Spinner } from '@/ui'

interface AuthCtx {
  user: User | null
  loading: boolean
  signIn: (r: AuthResult) => void
  signOut: () => Promise<void>
}
const Ctx = createContext<AuthCtx>(null as never)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(!!tokenStore.get())
  const qc = useQueryClient()

  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); qc.clear() })
    if (!tokenStore.get()) return
    api.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false))
  }, [qc])

  const signIn = useCallback((r: AuthResult) => { tokenStore.set(r.token); setUser(r.user) }, [])
  const signOut = useCallback(async () => {
    try { await api.logout() } catch { /* 忽略：本地照常清理 */ }
    tokenStore.clear(); setUser(null); qc.clear()
  }, [qc])

  const value = useMemo(() => ({ user, loading, signIn, signOut }), [user, loading, signIn, signOut])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />
  return <>{children}</>
}
