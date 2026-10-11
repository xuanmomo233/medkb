import type { Question, QuestionStat } from '@/api/types'
import { HtmlView } from '@/ui'
import { LETTERS } from '../lib'
import { isMulti } from './useQuizSession'
import s from './run.module.css'

interface Props {
  q: Question
  picked: string
  judged: boolean
  reveal: boolean
  stat?: QuestionStat
  onPick: (letter: string) => void
}

export default function OptionList({ q, picked, judged, reveal, stat, onPick }: Props) {
  const multi = isMulti(q)
  const total = stat ? Object.values(stat.dist).reduce((a, b) => a + b, 0) : 0
  return (
    <div className={s.options} role={multi ? 'group' : 'radiogroup'} aria-label="选项">
      {q.options_html.map((html, i) => {
        const L = LETTERS[i]
        const on = picked.includes(L)
        const isAns = reveal && q.answer.includes(L)
        const wrongPick = judged && on && !q.answer.includes(L)
        const missed = judged && isAns && !on
        const cls = [s.option, on && !judged && s.optSel, isAns && s.optGood, wrongPick && s.optBad, missed && s.optMiss].filter(Boolean).join(' ')
        const mark = wrongPick ? '✗' : isAns ? '✓' : on ? '●' : ''
        const rate = total && stat ? Math.round(((stat.dist[L] ?? 0) / total) * 100) : null
        return (
          <button key={L} type="button" className={cls} disabled={judged}
            role={multi ? 'checkbox' : 'radio'} aria-checked={on} onClick={() => onPick(L)}>
            <span className={s.optLetter}>{L}</span>
            <span className={s.optBody}>
              <HtmlView html={html} className={s.optText} />
              {judged && rate !== null && (
                <span className={s.optRate}>
                  <span className={s.optRateTrack}><span className={s.optRateFill} style={{ width: `${rate}%` }} /></span>
                  <span>{rate}%</span>
                </span>
              )}
            </span>
            <span className={s.optSide}>
              {missed && <span className={s.optTag}>漏选</span>}
              {wrongPick && <span className={s.optTag}>你的选择</span>}
              <span className={s.optMark} aria-hidden>{mark}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
