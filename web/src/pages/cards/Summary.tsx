import { Link } from 'react-router-dom'
import { Button, Card, Icon } from '@/ui'
import type { Rating } from './query'
import s from './run.module.css'

export default function Summary({ total, ratings, onRestart, onPrev }: {
  total: number; ratings: Record<number, Rating>; onRestart: () => void; onPrev: () => void
}) {
  const vals = Object.values(ratings)
  const count = (r: Rating) => vals.filter((v) => v === r).length
  const stats: { label: string; n: number; cls: string }[] = [
    { label: '忘了', n: count('rate_again'), cls: s.sBad },
    { label: '模糊', n: count('rate_hard'), cls: s.sWarn },
    { label: '记住', n: count('rate_good'), cls: s.sGood },
  ]
  const skipped = total - vals.length
  return (
    <Card className={s.summary}>
      <div className={s.sIcon} aria-hidden><Icon name="trophy" size={36} /></div>
      <h2>本轮完成</h2>
      <p className={s.sSub}>共 {total} 张{skipped > 0 ? `，其中 ${skipped} 张未评分` : ''}</p>
      <div className={s.sStats}>
        {stats.map((x) => <div key={x.label} className={`${s.sStat} ${x.cls}`}><b>{x.n}</b><span>{x.label}</span></div>)}
      </div>
      <div className={s.sActions}>
        <Button variant="primary" onClick={onRestart}>再来一轮</Button>
        <Button onClick={onPrev}>回看最后一张</Button>
        <Link to="/cards"><Button>返回挑选</Button></Link>
      </div>
    </Card>
  )
}
