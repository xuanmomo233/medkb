import { Link } from 'react-router-dom'
import { Card } from '@/ui'
import { Async } from './Async'
import { useTodayQuery } from './queries'
import s from './today.module.css'

interface Entry { label: string; count: number; to: string; tone: string }

export default function TodoCard() {
  const q = useTodayQuery()
  return (
    <Card title="待办入口">
      <Async q={q} height={150}>
        {({ counts: c }) => {
          const entries: Entry[] = [
            { label: '到期题', count: c.due, to: '/quiz/run?due=1', tone: 'info' },
            { label: '错题', count: c.wrong, to: '/quiz/run?wrong=1', tone: 'bad' },
            { label: '收藏题', count: c.starred, to: '/quiz/run?starred=1', tone: 'warn' },
            { label: '已掌握', count: c.mastered, to: '', tone: 'good' },
          ]
          return (
            <div className={s.tiles}>
              {entries.map((e) => {
                const inner = <><span className={s.big}>{e.count}</span><span>{e.label}</span></>
                const cls = `${s.tile} ${s[`t-${e.tone}`]}`
                return e.to
                  ? <Link key={e.label} to={e.to} className={cls}>{inner}</Link>
                  : <div key={e.label} className={cls}>{inner}</div>
              })}
              <div className={s.cardLinks}>
                <span className={s.sub}>背卡</span>
                <Link to="/cards/run?due=1" className={s.chip}>到期背卡</Link>
                <Link to="/cards/run?starred=1" className={s.chip}>收藏卡</Link>
              </div>
            </div>
          )
        }}
      </Async>
    </Card>
  )
}
