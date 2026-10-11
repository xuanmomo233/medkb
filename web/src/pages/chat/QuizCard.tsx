import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { ChatAnswerResult, ChatQuiz } from '@/api/types'
import { Button, HtmlView, useToast } from '@/ui'
import s from './chat.module.css'

interface Props { quiz: ChatQuiz; onResult: (r: ChatAnswerResult) => void }

export default function QuizCard({ quiz, onResult }: Props) {
  const nav = useNavigate()
  const toast = useToast()
  const [picked, setPicked] = useState<string[]>([])
  const [result, setResult] = useState<ChatAnswerResult | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (keys: string[]) => {
    setBusy(true)
    try {
      const r = await api.chatAnswer({ qid: quiz.qid, answer: [...keys].sort().join('') })
      setResult(r)
      onResult(r)
    } catch (e) {
      toast(e instanceof Error ? e.message : '提交失败', true)
    } finally { setBusy(false) }
  }

  const pick = (k: string) => {
    if (result || busy) return
    if (!quiz.multi) { setPicked([k]); void submit([k]); return }
    setPicked((p) => p.includes(k) ? p.filter((x) => x !== k) : [...p, k])
  }

  const cls = (k: string) => {
    const sel = picked.includes(k)
    if (!result) return `${s.opt} ${sel ? s.optSel : ''}`
    if (result.answer.includes(k)) return `${s.opt} ${s.optGood}`
    return `${s.opt} ${sel ? s.optBad : ''}`
  }

  return (
    <div className={s.quiz}>
      <div className={s.quizHead}>
        <span className={s.quizTag}>抽背题</span>
        <span>{quiz.system}{quiz.multi ? ' · 多选' : ''}</span>
      </div>
      <HtmlView html={quiz.stem_html} />
      <div className={s.opts}>
        {quiz.options.map((o) => (
          <button key={o.key} type="button" className={cls(o.key)} disabled={!!result || busy} onClick={() => pick(o.key)}>
            <span className={s.optKey}>{o.key}</span>
            <HtmlView html={o.html} className={s.optText} />
          </button>
        ))}
      </div>
      <div className={s.quizFoot}>
        {quiz.multi && !result && (
          <Button variant="primary" size="sm" disabled={!picked.length || busy} onClick={() => submit(picked)}>
            {busy ? '提交中…' : '提交'}
          </Button>
        )}
        {result && <span className={result.correct ? s.good : s.bad}>{result.correct ? '✓ 回答正确' : `✗ 回答错误，正确答案 ${result.answer}`}</span>}
        {!quiz.qid.startsWith('L') && (
          <Button variant="ghost" size="sm" onClick={() => nav(`/search?q=${encodeURIComponent(quiz.qid)}`)}>查看原题</Button>
        )}
      </div>
    </div>
  )
}
