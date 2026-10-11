import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Button } from '@/ui'
import { useAuth } from './auth'
import { useTheme } from './theme'
import s from './layout.module.css'

const NAV = [
  { to: '/', icon: '📅', label: '今日', end: true },
  { to: '/browse', icon: '📚', label: '目录' },
  { to: '/quiz', icon: '📝', label: '刷题' },
  { to: '/cards', icon: '🃏', label: '背卡' },
  { to: '/chat', icon: '🤖', label: 'AI 陪学' },
  { to: '/me', icon: '👤', label: '我的' },
]

export default function Layout() {
  const { user, signOut } = useAuth()
  const { theme, toggle } = useTheme()
  const nav = useNavigate()
  const [q, setQ] = useState('')

  return (
    <div className={s.shell}>
      <aside className={s.sidebar}>
        <div className={s.brand}><span className={s.logo}>⚕</span>医学知识库</div>
        <nav className={s.nav} aria-label="主导航">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${s.navItem} ${isActive ? s.navActive : ''}`}>
              <span className={s.navIcon}>{n.icon}</span>{n.label}
            </NavLink>
          ))}
        </nav>
        <div className={s.sideFoot}>
          <div className={s.user}>{user?.username}{user?.is_admin ? '（管理员）' : ''}</div>
          <Button variant="ghost" size="sm" onClick={() => void signOut()}>退出登录</Button>
        </div>
      </aside>

      <div className={s.main}>
        <header className={s.topbar}>
          <form style={{ flex: 1, display: 'flex' }} onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/search?q=${encodeURIComponent(q.trim())}`) }}>
            <input className={s.search} value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜题目 / 考点 / 章节…" aria-label="全局搜索" />
          </form>
          <div className={s.topRight}>
            <Button variant="ghost" size="sm" onClick={toggle} aria-label="切换主题" title="切换主题">{theme === 'dark' ? '☀️' : '🌙'}</Button>
          </div>
        </header>
        <main className={s.content}><Outlet /></main>
      </div>

      <nav className={s.bottomNav} aria-label="底部导航">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${s.bnItem} ${isActive ? s.bnActive : ''}`}>
            <span className={s.navIcon}>{n.icon}</span>{n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
