import type { Question, QuizMode } from '@/api/types'
import { Modal } from '@/ui'
import type { Ans } from './useQuizSession'
import s from './run.module.css'

interface Props {
  questions: Question[]
  ans: Record<number, Ans>
  idx: number
  mode: QuizMode
  onGo: (i: number) => void
  onClose: () => void
}

export default function JumpGrid({ questions, ans, idx, mode, onGo, onClose }: Props) {
  const test = mode === 'test'
  return (
    <Modal title="题号跳转" onClose={onClose} sheet>
      <div className={s.grid}>
        {questions.map((q, i) => {
          const a = ans[q.id]
          const state = test ? (a?.picked ? s.cellDone : '') : a?.judged ? (a.correct ? s.cellGood : s.cellBad) : ''
          const label = test ? (a?.picked ? '已答' : '未答') : a?.judged ? (a.correct ? '答对' : '答错') : '未做'
          return (
            <button key={q.id} type="button" className={`${s.cell} ${state} ${i === idx ? s.cellCur : ''}`}
              aria-label={`第 ${i + 1} 题，${label}`} aria-current={i === idx} onClick={() => { onGo(i); onClose() }}>
              {i + 1}
              {!test && a?.judged && <span className={s.cellMark} aria-hidden>{a.correct ? '✓' : '✗'}</span>}
            </button>
          )
        })}
      </div>
      <div className={s.legend}>
        {test ? <><span className={s.lgDone}>已答</span><span>未答</span></> : <><span className={s.lgGood}>✓ 答对</span><span className={s.lgBad}>✗ 答错</span><span>未做</span></>}
        <span className={s.lgCur}>当前</span>
      </div>
    </Modal>
  )
}
