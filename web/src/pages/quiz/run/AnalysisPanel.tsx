import type { Question, QuestionFull, QuestionStat } from '@/api/types'
import { Badge, Button, HtmlView, ProgressBar, Spinner } from '@/ui'
import QuestionExtras from './QuestionExtras'
import s from './run.module.css'

interface Props {
  q: Question
  picked: string
  judged: boolean
  correct: boolean | null
  full?: QuestionFull
  failed: boolean
  stat?: QuestionStat
  aiBusy: boolean
  onRetry: () => void
  onAi: () => void
}

export default function AnalysisPanel({ q, picked, judged, correct, full, failed, stat, aiBusy, onRetry, onAi }: Props) {
  const st = stat ?? full?.stat
  const rate = st && st.total ? Math.round((st.correct / st.total) * 100) : null
  return (
    <section className={s.analysis} aria-label="答案与解析">
      <div className={s.answerRow}>
        <span>正确答案 <strong className={s.answerText}>{q.answer}</strong></span>
        {judged && picked && <span className={s.mine}>你的选择 {picked}</span>}
        {judged && (correct
          ? <Badge tone="good">✓ 回答正确</Badge> : <Badge tone="bad">✗ 回答错误</Badge>)}
      </div>

      {rate !== null && st && (
        <div className={s.statRow}>
          <span className={s.statLabel}>全站正确率 {rate}%（{st.correct}/{st.total}）</span>
          <ProgressBar value={rate} tone={rate >= 60 ? 'good' : 'bad'} />
        </div>
      )}

      {!full && !failed && <Spinner />}
      {failed && !full && (
        <div className={s.inlineErr}>解析加载失败 <Button size="sm" onClick={onRetry}>重试</Button></div>
      )}

      {full && (full.analysis_html ? (
        <div className={s.analysisBody}>
          <div className={s.sectionTitle}>解析</div>
          <HtmlView html={full.analysis_html} />
        </div>
      ) : (
        <div className={s.analysisBody}>
          <div className={s.sectionTitle}>本题暂无解析</div>
          {full.related_cards.map((c) => (
            <div key={c.id} className={s.related}>
              <div className={s.relatedTerm}>{c.term}{c.hint && <span className={s.relatedHint}>{c.hint}</span>}</div>
              <HtmlView html={c.body_html} />
            </div>
          ))}
          <Button variant="primary" onClick={onAi} disabled={aiBusy}>{aiBusy ? 'AI 生成中…' : '✨ AI 生成解析'}</Button>
        </div>
      ))}

      {q.tags.length > 0 && (
        <div className={s.tags}>{q.tags.map((t) => <Badge key={t} tone="info">{t}</Badge>)}</div>
      )}
      <QuestionExtras question={q} />
    </section>
  )
}
