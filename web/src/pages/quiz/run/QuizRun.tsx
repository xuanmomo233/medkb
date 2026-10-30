import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Badge, Button, EmptyState, ErrorState, HtmlView, Icon, Modal, ProgressBar, Spinner } from '@/ui'
import { MODES, parseRun } from '../lib'
import AnalysisPanel from './AnalysisPanel'
import JumpGrid from './JumpGrid'
import OptionList from './OptionList'
import QuestionToolbar from './QuestionToolbar'
import { hasOptions, isMulti, useQuizSession } from './useQuizSession'
import { useQuizKeys } from './useQuizKeys'
import s from './run.module.css'
import { useScheduleNavigation } from '../../today/useScheduleNavigation'
import ScheduleJumpGrid from '../../today/ScheduleJumpGrid'
import { optionLabels } from '@/optionLabels'

function fmtRemain(sec: number) {
  const h = Math.floor(sec / 3600)
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0')
  const r = String(sec % 60).padStart(2, '0')
  return h ? `${h}:${m}:${r}` : `${m}:${r}`
}

export default function QuizRun() {
  const [sp] = useSearchParams()
  const search = sp.toString()
  return <QuizExercise key={search} search={search} />
}

export function QuizExercise({ search, onBack, embedded = false, exactIds = false }: { search: string; onBack?: () => void; embedded?: boolean; exactIds?: boolean }) {
  const nav = useNavigate()
  const schedule = useScheduleNavigation(!embedded && !onBack)
  const scheduledQuestionId = schedule.active ? schedule.items[schedule.index]?.item_id : undefined
  const p = useMemo(() => {
    const parsed = parseRun(new URLSearchParams(search))
    if (scheduledQuestionId) parsed.query.ids = [scheduledQuestionId]
    return parsed
  }, [search, scheduledQuestionId])
  const S = useQuizSession(search, p, schedule.scope, schedule.next, exactIds)
  const [jump, setJump] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const { q, cur } = S
  const contentRef = useRef<HTMLDivElement>(null)
  const touch = useRef<{ x: number; y: number } | null>(null)
  const { mode } = p
  const test = mode === 'test'
  const total = S.questions.length
  const navigationTotal = schedule.active ? schedule.total : total
  const navigationIndex = schedule.active ? schedule.index : S.idx
  const go = schedule.active ? schedule.go : S.go
  const judged = !!cur?.judged
  const multiPending = !!q && isMulti(q) && !test && mode !== 'recite' && !judged
  const showPaging = schedule.active || !embedded || total > 1
  const showBottom = showPaging || multiPending || mode === 'recite' || test

  useEffect(() => {
    if (embedded) contentRef.current?.scrollTo({ top: 0 })
    else window.scrollTo({ top: 0 })
  }, [embedded, q?.id])

  useQuizKeys({
    enabled: S.status === 'ready' && !jump && !confirm, mode, optionLabels: q ? optionLabels(q.options_html.length, q.option_labels) : [],
    prev: () => go(navigationIndex - 1), next: () => go(navigationIndex + 1), pick: S.pick, confirm: S.confirmMulti,
    reveal: S.toggleReveal, star: () => S.toggleMark('star'),
  })

  if (schedule.error) return <ErrorState error={schedule.error} onRetry={schedule.reload} />
  if (schedule.pending) return <Spinner />
  if (schedule.active && schedule.index < 0) return <EmptyState text="这份日程已更新，请返回今日重新进入" action={<Button onClick={() => nav('/')}>返回今日</Button>} />
  if (S.status === 'loading') return <Spinner />
  if (S.status === 'error') return <ErrorState error={S.error} onRetry={S.reload} />
  if (!q) return <EmptyState text={p.query.plan_day !== undefined ? '本批计划题目已完成' : '没有符合条件的题目'} action={<Button onClick={() => nav(p.query.plan_day !== undefined ? '/' : '/quiz')}>返回</Button>} />

  const reveal = judged || (mode === 'recite' && S.revealed) || !hasOptions(q)
  const showAnalysis = S.showFull && (mode !== 'recite' || S.revealed)
  const unanswered = total - S.answeredCount
  const modeLabel = MODES.find((m) => m.value === mode)?.label ?? ''
  const siblings = q.case_group ? S.questions
    .map((question, index) => ({ question, index }))
    .filter(({ question }) => question.case_group === q.case_group) : []

  return (
    <div className={`${s.wrap} ${embedded ? s.embedded : ''}`}>
      <div ref={contentRef} className={s.content}>
      <header className={s.top}>
        <Button variant="ghost" size="sm" onClick={onBack ?? (() => nav(schedule.active ? '/' : '/quiz'))} aria-label="返回"><Icon name="chevLeft" size={14} /> 返回</Button>
        <span className={s.topTitle}>{schedule.active ? '今日日程' : p.title || modeLabel}</span>
        {!test && <Button size="sm" variant="ghost" onClick={S.resetSession}>{schedule.active ? '重做本题' : '本次重练'}</Button>}
        {test && S.remaining !== null && (
          <span className={`${s.timer} ${S.remaining < 300 ? s.timerWarn : ''}`} role="timer" aria-label="剩余时间"><Icon name="clock" size={13} /> {fmtRemain(S.remaining)}</span>
        )}
        {test && <span className={s.topMeta}>已答 {S.answeredCount}/{total}</span>}
        {!schedule.active && <Button size="sm" onClick={() => setJump(true)} aria-label="题号跳转">{navigationIndex + 1} / {navigationTotal} <Icon name="grid" size={13} /></Button>}
      </header>
      <ProgressBar value={((navigationIndex + 1) / navigationTotal) * 100} />

      {S.resumeAt !== null && (
        <div className={s.resume} role="status">
          <span>上次做到第 {S.resumeAt + 1} 题</span>
          <Button size="sm" variant="primary" onClick={S.jumpResume}>跳转</Button>
          <Button size="sm" variant="ghost" onClick={S.dismissResume}>忽略</Button>
        </div>
      )}

      <article className={s.card}
        onTouchStart={(event) => {
          touch.current = event.touches.length === 1 && !(event.target as Element).closest('button, a, input, textarea, table, [role="radio"], [role="checkbox"]')
            ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null
        }}
        onTouchEnd={(event) => {
          const start = touch.current
          touch.current = null
          if (!start || !event.changedTouches.length || window.getSelection()?.toString()) return
          const dx = event.changedTouches[0].clientX - start.x
          const dy = event.changedTouches[0].clientY - start.y
          if (Math.abs(dx) > 80 && Math.abs(dx) > Math.abs(dy) * 1.8) go(navigationIndex + (dx < 0 ? 1 : -1))
        }}>
        <div className={s.badges}>
          <Badge tone="brand">{q.qtype}{isMulti(q) && !q.qtype.includes('多') && !q.qtype.includes('X') ? '（多选）' : ''}</Badge>
          <Badge>{q.system}</Badge>
          <Badge>{q.chapter}</Badge>
          <span className={s.qid}>{q.qid}</span>
        </div>
        {q.parent_html && <div className={s.parent}>
          <strong>共用题干{q.case_total ? ` · ${q.case_total} 个子题` : ''}</strong>
          <HtmlView html={q.parent_html} />
          {!schedule.active && siblings.length > 1 && <nav className={s.caseNav} aria-label="本病例子题">
            {siblings.map(({ question, index }) => (
              <Button key={question.id} size="sm" variant={question.id === q.id ? 'primary' : 'default'}
                aria-current={question.id === q.id ? 'step' : undefined} onClick={() => S.go(index)}>
                子题 {question.case_index}{S.ans[question.id]?.picked ? ' · 已答' : ''}
              </Button>
            ))}
          </nav>}
        </div>}
        <HtmlView html={q.stem_html} className={s.stem} />
        {hasOptions(q) && (
          <OptionList q={q} picked={cur?.picked ?? ''} judged={judged} reveal={reveal && (judged || S.revealed)}
            stat={S.stats[q.id] ?? S.full[q.id]?.stat} onPick={S.pick} />
        )}
        {mode === 'recite' && !S.revealed && <p className={s.hide}>答案已隐藏，按空格或点击下方按钮显示</p>}
        <QuestionToolbar q={q} canRedo={!test && judged} onToggle={S.toggleMark} onRedo={S.redo} />
      </article>

      {showAnalysis && (
        <AnalysisPanel q={q} picked={cur?.picked ?? ''} judged={judged} correct={cur?.correct ?? null} full={S.full[q.id]}
          allowRelated={!test}
          failed={!!S.fullErr[q.id]} stat={S.stats[q.id]} aiBusy={S.aiBusy} onRetry={() => S.loadFull(q.id)} onAi={S.genAnalysis}
          onEdited={() => { void S.refreshFull(q.id) }} />
      )}

      </div>
      {showBottom && <nav className={`${s.bottom} ${schedule.active ? s.scheduleBottom : ''}`} aria-label="题目导航">
        {showPaging && <Button onClick={() => go(navigationIndex - 1)} disabled={navigationIndex === 0}><Icon name="chevLeft" size={14} /> 上一题</Button>}
        {schedule.active && <Button onClick={() => setJump(true)} aria-label="题号跳转">{navigationIndex + 1} / {navigationTotal} <Icon name="grid" size={14} /></Button>}
        {multiPending && <Button className={s.answerAction} variant="primary" disabled={!cur?.picked} onClick={S.confirmMulti}>提交答案</Button>}
        {mode === 'recite' && <Button className={s.answerAction} onClick={S.toggleReveal}>{S.revealed ? '隐藏答案' : '显示答案'}</Button>}
        {test && <Button className={s.answerAction} variant="primary" onClick={() => setConfirm(true)} disabled={S.submitting}>交卷</Button>}
        {showPaging && <Button onClick={() => schedule.active && navigationIndex === navigationTotal - 1 ? nav('/') : go(navigationIndex + 1)} disabled={!schedule.active && navigationIndex >= navigationTotal - 1}>{schedule.active && navigationIndex === navigationTotal - 1 ? '返回今日' : '下一题'} <Icon name="chevRight" size={14} /></Button>}
      </nav>}

      {jump && (schedule.active ? <ScheduleJumpGrid navigation={schedule} onClose={() => setJump(false)} /> : <JumpGrid questions={S.questions} ans={S.ans} idx={S.idx} mode={mode} onGo={S.go} onClose={() => setJump(false)} />)}
      {confirm && (
        <Modal title="确认交卷" onClose={() => setConfirm(false)}>
          <p className={s.confirmText}>{unanswered > 0 ? `还有 ${unanswered} 题未作答，未答题按错误计分。` : '所有题目均已作答。'}确定现在交卷吗？</p>
          <div className={s.confirmBtns}>
            <Button onClick={() => setConfirm(false)}>继续答题</Button>
            <Button variant="primary" disabled={S.submitting} onClick={() => void S.submit()}>{S.submitting ? '交卷中…' : '确认交卷'}</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}
