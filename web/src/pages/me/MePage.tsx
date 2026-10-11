import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { Badge, Button, Card, Modal, PageHeader } from '@/ui'
import s from './me.module.css'

const tiles = [
  { to: '/me/notes', icon: '📝', title: '我的笔记', sub: '题目与卡片笔记' },
  { to: '/quiz/wrongbook', icon: '❌', title: '错题本', sub: '按章节复习错题' },
  { to: '/quiz/exams', icon: '📊', title: '成绩记录', sub: '模拟考试历史' },
  { to: '/me/settings', icon: '⚙️', title: '学习设置', sub: '目标、阈值与外观' },
]

export default function MePage() {
  const { user, signOut } = useAuth()
  const nav = useNavigate()
  const [confirm, setConfirm] = useState(false)
  return (
    <div className={s.wrap}>
      <PageHeader title="我的" />
      <Card>
        <div className={s.profile}>
          <div className={s.avatar}>{user?.username.slice(0, 1).toUpperCase()}</div>
          <div className={s.name}>{user?.username}{user?.is_admin && <Badge tone="warn">管理员</Badge>}</div>
        </div>
      </Card>
      <div className={s.grid}>
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className={s.tile}>
            <span className={s.tileIcon}>{t.icon}</span>
            <span className={s.tileTitle}>{t.title}</span>
            <span className={s.tileSub}>{t.sub}</span>
          </Link>
        ))}
        <button type="button" className={s.tile} onClick={() => setConfirm(true)}>
          <span className={s.tileIcon}>🚪</span>
          <span className={s.tileTitle}>退出登录</span>
          <span className={s.tileSub}>切换账号</span>
        </button>
      </div>
      {confirm && (
        <Modal title="退出登录" onClose={() => setConfirm(false)}>
          <p style={{ marginBottom: 16 }}>确定要退出当前账号吗？</p>
          <div className={s.saveBar}>
            <Button onClick={() => setConfirm(false)}>取消</Button>
            <Button variant="danger" onClick={async () => { await signOut(); nav('/login', { replace: true }) }}>退出</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}
