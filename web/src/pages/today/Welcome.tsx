import { Link } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { useTodayQuery } from './queries'
import s from './today.module.css'

function greeting() {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

export default function Welcome() {
  const { user } = useAuth()
  const { data } = useTodayQuery()
  const left = data?.exam_days_left
  return (
    <section className={s.welcome}>
      <div>
        <h1>{greeting()}，{user?.username ?? '同学'}</h1>
        <p className={s.sub}>保持节奏，今天也向目标靠近一步。</p>
      </div>
      <div className={s.countdown} aria-live="polite">
        {!data ? <span className={s.sub}>&nbsp;</span> : left == null ? (
          <Link to="/me/settings" className={s.link}>设置考试日期，开启倒计时 →</Link>
        ) : (
          <><span className={s.sub}>距考试还有</span><strong className={s.big}>{left}</strong><span className={s.sub}>天</span></>
        )}
      </div>
    </section>
  )
}
