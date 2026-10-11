import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Button, Icon } from '@/ui'
import type { IconName } from '@/ui'
import { useAuth } from './auth'
import { useTheme } from './theme'
import s from './layout.module.css'

const NAV: { to: string; icon: IconName; label: string; end?: boolean }[] = [
  { to: '/', icon: 'calendar', label: '今日', end: true },
  { to: '/browse', icon: 'book', label: '目录' },
  { to: '/quiz', icon: 'quiz', label: '刷题' },
  { to: '/cards', icon: 'cards', label: '背卡' },
  { to: '/chat', icon: 'robot', label: 'AI 陪学' },
  { to: '/me', icon: 'user', label: '我的' },
]

export default function Layout() {
  const { user, signOut } = useAuth()
  const { theme, toggle } = useTheme()
  const nav = useNavigate()
  const [q, setQ] = useState('')

  return (
    <div className={s.shell}>
      <aside className={s.sidebar}>
        <div className={s.brand}><span className={s.logo}><Icon name="med" size={22} /></span>医学知识库</div>
        <nav className={s.nav} aria-label="主导航">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${s.navItem} ${isActive ? s.navActive : ''}`}>
              <span className={s.navIcon}><Icon name={n.icon} size={18} /></span>{n.label}
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
            <Button variant="ghost" size="sm" onClick={toggle} aria-label="切换主题" title="切换主题"><Icon name={theme === 'dark' ? 'sun' : 'moon'} size={17} /></Button>
          </div>
        </header>
        <main className={s.content}><Outlet /></main>
      </div>

      <nav className={s.bottomNav} aria-label="底部导航">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${s.bnItem} ${isActive ? s.bnActive : ''}`}>
            <span className={s.navIcon}><Icon name={n.icon} size={19} /></span>{n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
