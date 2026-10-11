import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import type { ExamReport } from '@/api/types'
import { Button, Card, EmptyState, PageHeader, ProgressBar, Segmented } from '@/ui'
import { toSearch } from './lib'
import s from './report.module.css'

interface ReportState { report: ExamReport; title: string }

export default function Report() {
  const nav = useNavigate()
  const st = useLocation().state as ReportState | null
  const [redoMode, setRedoMode] = useState<'practice' | 'test'>('practice')
  if (!st?.report) return <Navigate to="/quiz" replace />
  const { report: r, title } = st
  const wrong = r.wrong_ids.length
  const unjudged = r.results.filter((x) => !x.judged).length

  return (
    <div className={s.page}>
      <PageHeader title="成绩单" sub={title} extra={<Button onClick={() => nav('/quiz')}>返回</Button>} />

      <Card>
        <div className={s.scores}>
          <div className={s.score}>
            <span className={s.big}>{r.score_100}</span>
            <span className={s.label}>百分制得分</span>
          </div>
          <div className={s.score}>
            <span className={s.big}>{r.score_300}</span>
            <span className={s.label}>折算 300 分制</span>
          </div>
          <div className={s.score}>
            <span className={s.big}>{r.correct}<small>/{r.total}</small></span>
            <span className={s.label}>答对 / 总题数</span>
          </div>
        </div>
        {unjudged > 0 && <p className={s.note}>其中 {unjudged} 题未作答，按错误计分。</p>}
      </Card>

      <Card title="分章节正确率">
        {r.by_chapter.length === 0 ? <EmptyState icon="📋" text="没有可统计的作答" /> : (
          <div className={s.chapters}>
            {r.by_chapter.map((c) => {
              const bad = c.rate < 60
              return (
                <div key={c.chapter} className={s.chapter}>
                  <div className={s.chapterHead}>
                    <span>{c.chapter}</span>
                    <span className={bad ? s.bad : s.good}>{bad ? '✗ ' : '✓ '}{c.correct}/{c.total} · {Math.round(c.rate)}%</span>
                  </div>
                  <ProgressBar value={c.rate} tone={bad ? 'bad' : 'good'} />
                </div>
              )
            })}
          </div>
        )}
      </Card>

      <Card title="错题回顾" extra={<span className={s.label}>共 {wrong} 题</span>}>
        {wrong === 0 ? <EmptyState icon="🎉" text="全部答对，太棒了" /> : (
          <div className={s.redo}>
            <Segmented value={redoMode} onChange={setRedoMode} options={[{ value: 'practice', label: '练习模式' }, { value: 'test', label: '测试模式' }]} />
            <Button variant="primary" onClick={() => nav(`/quiz/run?${toSearch({ ids: r.wrong_ids, mode: redoMode, title: '错题重做' })}`)}>重做错题</Button>
          </div>
        )}
      </Card>
    </div>
  )
}
