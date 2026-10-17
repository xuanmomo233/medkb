import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { invalidateStudy } from '../../today/invalidateStudy'
import { api } from '@/api/endpoints'
import type { ProgressState, Question, QuestionFull, QuestionStat } from '@/api/types'
import { useToast } from '@/ui'
import { hashStr, LETTERS, readJson, sortLetters, type RunParams } from '../lib'

export interface Ans { picked: string; judged: boolean; correct: boolean | null }
export type MarkKind = 'star' | 'wrong' | 'master' | 'plan'
interface Patch { state?: ProgressState; starred?: boolean }
interface TestSave { sig: string; picks: Record<number, string>; deadline: number | null; idx: number }

export const isMulti = (q: Question) => q.answer.length > 1 && /^[A-H]+$/.test(q.answer)
export const hasOptions = (q: Question) => q.options_html.length > 0 && /^[A-H]+$/.test(q.answer)

export function useQuizSession(search: string, p: RunParams) {
  const nav = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { query, mode, mins, title } = p
  const hash = hashStr(search)
  const testKey = `quiz.test.${hash}`
  const posKey = `quiz.pos.${hash}`
  const trackPos = mode !== 'test' && !query.random && !query.shuffle && query.plan_day === undefined && !query.fresh

  const [questions, setQuestions] = useState<Question[]>([])
  const [status, setStatus] = useState<'loading' | 'error' | 'ready'>('loading')
  const [error, setError] = useState<unknown>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [idx, setIdx] = useState(0)
  const [ans, setAns] = useState<Record<number, Ans>>({})
  const [full, setFull] = useState<Record<number, QuestionFull>>({})
  const [fullErr, setFullErr] = useState<Record<number, boolean>>({})
  const [stats, setStats] = useState<Record<number, QuestionStat>>({})
  const [patch, setPatch] = useState<Record<number, Patch>>({})
  const [aiBusy, setAiBusy] = useState(false)
  const [revealed, setRevealed] = useState(true)
  const [deadline, setDeadline] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [submitting, setSubmitting] = useState(false)
  const [resumeAt, setResumeAt] = useState<number | null>(null)
  const fullReq = useRef(new Set<number>())
  const quickTimer = useRef<number>(0)
  const submitted = useRef(false)

  useEffect(() => {
    let off = false
    api.questions({ ...query, lite: true }).then((list) => {
      if (off) return
      const next: Record<number, Ans> = {}
      let i = 0
      const sig = hashStr(list.map((q) => q.id).join(','))
      const saved = mode === 'test' ? readJson<TestSave>(sessionStorage, testKey) : null
      if (mode === 'test') {
        const ok = saved && saved.sig === sig
        for (const q of list) {
          const picked = ok ? saved.picks[q.id] ?? '' : ''
          if (picked) next[q.id] = { picked, judged: false, correct: null }
        }
        i = ok ? Math.min(saved.idx, list.length - 1) : 0
        setDeadline(ok ? saved.deadline : mins ? Date.now() + mins * 60000 : null)
      } else {
        for (const q of list) if (q.done && q.last_picked) next[q.id] = { picked: q.last_picked, judged: true, correct: q.last_correct }
        const pos = trackPos ? Number(localStorage.getItem(posKey)) : 0
        if (pos > 0 && pos < list.length) setResumeAt(pos)
      }
      setQuestions(list)
      setAns(next)
      setIdx(i)
      setStatus('ready')
    }, (e: unknown) => { if (!off) { setError(e); setStatus('error') } })
    return () => { off = true }
  }, [query, mode, mins, testKey, posKey, trackPos, reloadKey])

  const q: Question | undefined = useMemo(() => {
    const base = questions[idx]
    return base ? { ...base, ...patch[base.id] } : undefined
  }, [questions, idx, patch])

  const loadFull = useCallback((id: number) => {
    if (fullReq.current.has(id)) return
    fullReq.current.add(id)
    setFullErr((m) => (m[id] ? { ...m, [id]: false } : m))
    api.questionFull(id).then((f) => setFull((m) => ({ ...m, [id]: f })), () => {
      fullReq.current.delete(id)
      setFullErr((m) => ({ ...m, [id]: true }))
    })
  }, [])

  const refreshFull = useCallback(async (id: number) => {
    try {
      const f = await api.questionFull(id)
      setFull((m) => ({ ...m, [id]: f }))
      setStats((m) => ({ ...m, [id]: f.stat }))
      setFullErr((m) => {
        if (!m[id]) return m
        const { [id]: _, ...rest } = m
        void _
        return rest
      })
      setQuestions((qs) => qs.map((q) => q.id === id ? {
        ...q, stem_html: f.stem_html, system: f.system, tags: f.tags,
        analysis_html: f.analysis_html, analysis_empty: f.analysis_empty,
      } : q))
    } catch (e) {
      setFullErr((m) => ({ ...m, [id]: true }))
      toast(e instanceof Error ? e.message : '已保存，但刷新题目失败，请重试', true)
    }
  }, [toast])

  const cur = q ? ans[q.id] : undefined
  const showFull = !!q && (mode === 'recite' || !!cur?.judged || !hasOptions(q))

  useEffect(() => {
    if (!q) return
    if (showFull) loadFull(q.id)
    if (mode !== 'test') for (const n of questions.slice(idx + 1, idx + 3)) loadFull(n.id)
  }, [q, showFull, mode, questions, idx, loadFull])

  useEffect(() => {
    window.clearTimeout(quickTimer.current)
    setRevealed(true)
    if (trackPos && status === 'ready') localStorage.setItem(posKey, String(idx))
  }, [idx, trackPos, posKey, status])

  useEffect(() => {
    if (mode !== 'test' || status !== 'ready') return
    const picks: Record<number, string> = {}
    for (const [id, a] of Object.entries(ans)) picks[Number(id)] = a.picked
    const sig = hashStr(questions.map((x) => x.id).join(','))
    sessionStorage.setItem(testKey, JSON.stringify({ sig, picks, deadline, idx } satisfies TestSave))
  }, [mode, status, ans, deadline, idx, questions, testKey])

  const go = useCallback((i: number) => setIdx(Math.max(0, Math.min(questions.length - 1, i))), [questions.length])

  const judge = useCallback((question: Question, picked: string) => {
    const correct = sortLetters(picked) === sortLetters(question.answer)
    setAns((m) => ({ ...m, [question.id]: { picked, judged: true, correct } }))
    api.attempt({ question_id: question.id, picked: [...picked].map((c) => LETTERS.indexOf(c)) })
      .then((r) => { setStats((m) => ({ ...m, [question.id]: r.stat })); void invalidateStudy(queryClient) }, () => toast('作答记录保存失败', true))
    if (mode === 'quick' && correct) {
      const at = idx
      quickTimer.current = window.setTimeout(() => setIdx((i) => (i === at ? Math.min(i + 1, questions.length - 1) : i)), 600)
    }
  }, [mode, idx, questions.length, toast, queryClient])

  const pick = useCallback((letter: string) => {
    if (!q || !hasOptions(q) || mode === 'recite' || cur?.judged) return
    const multi = isMulti(q)
    const old = cur?.picked ?? ''
    const picked = multi ? (old.includes(letter) ? old.replace(letter, '') : sortLetters(old + letter)) : letter
    if (!multi && mode !== 'test') { judge(q, picked); return }
    setAns((m) => ({ ...m, [q.id]: { picked, judged: false, correct: null } }))
  }, [q, mode, cur, judge])

  const confirmMulti = useCallback(() => {
    if (q && cur && !cur.judged && mode !== 'test' && cur.picked) judge(q, cur.picked)
  }, [q, cur, mode, judge])

  const redo = useCallback(() => {
    if (!q) return
    setAns((m) => { const { [q.id]: _, ...rest } = m; void _; return rest })
  }, [q])

  const toggleMark = useCallback((kind: MarkKind) => {
    if (!q) return
    const prev: Patch = { state: q.state, starred: q.starred }
    const isOn = kind === 'star' ? q.starred : q.state === { wrong: 'again', master: 'mastered', plan: 'plan' }[kind]
    const action = isOn ? ({ star: 'unstar', wrong: 'unwrong', master: 'unmaster', plan: 'unplan' } as const)[kind] : kind
    const next: Patch = kind === 'star' ? { starred: !isOn }
      : { state: isOn ? '' : ({ wrong: 'again', master: 'mastered', plan: 'plan' } as const)[kind] }
    setPatch((m) => ({ ...m, [q.id]: { ...m[q.id], ...next } }))
    api.mark({ target_type: 'question', target_id: q.id, action }).then(() => invalidateStudy(queryClient)).catch(() => {
      setPatch((m) => ({ ...m, [q.id]: { ...m[q.id], ...prev } }))
      toast('操作失败，已恢复', true)
    })
  }, [q, toast, queryClient])

  const genAnalysis = useCallback(async () => {
    if (!q || aiBusy) return
    setAiBusy(true)
    try {
      const r = await api.aiAnalysis(q.id)
      setFull((m) => (m[q.id] ? { ...m, [q.id]: { ...m[q.id], analysis_html: r.analysis_html, analysis_empty: false } } : m))
    } catch (e) {
      toast(e instanceof Error ? e.message : 'AI 解析生成失败', true)
    } finally {
      setAiBusy(false)
    }
  }, [q, aiBusy, toast])

  const answeredCount = useMemo(() => questions.filter((x) => ans[x.id]?.picked).length, [questions, ans])

  const submit = useCallback(async () => {
    if (submitted.current) return
    submitted.current = true
    setSubmitting(true)
    try {
      const items = questions.map((x) => ({ question_id: x.id, picked: [...(ans[x.id]?.picked ?? '')].map((c) => LETTERS.indexOf(c)) }))
      const name = title || '测试'
      const report = await api.submitExam({ title: name, items })
      void invalidateStudy(queryClient)
      sessionStorage.removeItem(testKey)
      nav('/quiz/report', { state: { report, title: name }, replace: true })
    } catch (e) {
      submitted.current = false
      setSubmitting(false)
      toast(e instanceof Error ? e.message : '交卷失败，请重试', true)
    }
  }, [questions, ans, title, testKey, nav, toast, queryClient])

  useEffect(() => {
    if (!deadline || status !== 'ready') return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [deadline, status])

  const remaining = deadline ? Math.max(0, Math.ceil((deadline - now) / 1000)) : null
  useEffect(() => {
    if (remaining === 0 && status === 'ready') { toast('时间到，已自动交卷'); void submit() }
  }, [remaining, status, submit, toast])

  const dismissResume = () => setResumeAt(null)
  const jumpResume = () => { if (resumeAt !== null) go(resumeAt); setResumeAt(null) }

  return {
    status, error, reload: () => { setStatus('loading'); setReloadKey((k) => k + 1) },
    questions, idx, q, cur, ans, full, fullErr, stats, showFull, revealed,
    toggleReveal: () => setRevealed((v) => !v), loadFull, refreshFull, go, pick, confirmMulti, redo, toggleMark, genAnalysis, aiBusy,
    answeredCount, remaining, submit, submitting, resumeAt, dismissResume, jumpResume,
  }
}
