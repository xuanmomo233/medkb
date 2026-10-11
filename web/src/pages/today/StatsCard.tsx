import { Card, EmptyState } from '@/ui'
import { Async } from './Async'
import { useStatsQuery } from './queries'
import { pct, toneOf } from './utils'
import s from './today.module.css'

export default function StatsCard() {
  const q = useStatsQuery()
  return (
    <Card title="学习统计">
      <Async q={q} height={240}>
        {(d) => {
          const max = Math.max(1, ...d.daily.map((x) => x.count))
          return (
            <div className={s.stack}>
              <div className={s.statRow}>
                <div><span className={s.big}>{d.attempted}</span><span className={s.sub}> 已做题</span></div>
                <div><span className={s.big}>{pct(d.accuracy)}%</span><span className={s.sub}> 总正确率</span></div>
              </div>
              <div>
                <div className={s.meta}>近 30 天做题量</div>
                {d.daily.every((x) => x.count === 0) ? <EmptyState icon="quiz" text="近 30 天暂无做题记录" /> : (
                  <div className={s.chart} role="img" aria-label="近 30 天做题柱状图">
                    {d.daily.map((x) => (
                      <div key={x.day} className={s.chartCol} title={`${x.day}：${x.count} 题，答对 ${x.correct}`}>
                        <div className={s.chartBar} style={{ height: `${(x.count / max) * 100}%` }} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className={s.stack}>
                <div className={s.meta}>各系统正确率</div>
                {d.by_system.map((x) => (
                  <div key={x.system} className={s.sysRow}>
                    <span>{x.system}</span>
                    <div className={s.bar}><div className={`${s.barFill} ${s[`f-${toneOf(x.rate)}`]}`} style={{ width: `${pct(x.rate)}%` }} /></div>
                    <span className={s.num}>{pct(x.rate)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )
        }}
      </Async>
    </Card>
  )
}

