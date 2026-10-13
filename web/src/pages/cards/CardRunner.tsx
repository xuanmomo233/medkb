import { useCallback, useEffect, useRef, useState } from 'react'
import type { TouchEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { Card, CardQuery } from '@/api/types'
import { useAuth } from '@/app/auth'
import { AdminCardEditSheet, NoteSheet } from '@/features/notes'
import { Button, Icon, Modal, ProgressBar, useToast } from '@/ui'
import CardFace from './CardFace'
import { queryTitle } from './query'
import type { Rating } from './query'
import Summary from './Summary'
import s from './run.module.css'

interface Saved { idx: number; ratings: Record<number, Rating> }
interface Props { cards: Card[]; query: CardQuery; storeKey: string; onRestart: () => void }

const RATES: { action: Rating; label: string; key: string; cls: string }[] = [
  { action: 'rate_again', label: '忘了', key: '1', cls: s.rBad },
  { action: 'rate_hard', label: '模糊', key: '2', cls: s.rWarn },
  { action: 'rate_good', label: '记住', key: '3', cls: s.rGood },
]

function restore(key: string, total: number): Saved {
  try {
    const v = JSON.parse(sessionStorage.getItem(`cards.pos:${key}`) ?? 'null') as Saved | null
    if (v && v.idx >= 0 && v.idx <= total) return v
  } catch { /* 忽略损坏的缓存 */ }
  return { idx: 0, ratings: {} }
}

export default function CardRunner({ cards: initial, query, storeKey, onRestart }: Props) {
  const toast = useToast()
  const { user } = useAuth()
  const [cards, setCards] = useState(initial)
  const [saved] = useState(() => restore(storeKey, initial.length))
  const [idx, setIdx] = useState(saved.idx)
  const [ratings, setRatings] = useState(saved.ratings)
  const [flipped, setFlipped] = useState(false)
  const [jump, setJump] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [noteOpen, setNoteOpen] = useState(false)
  const touch = useRef<{ x: number; y: number } | null>(null)
  const total = cards.length
  const done = idx >= total
  const card = done ? null : cards[idx]

  useEffect(() => {
    sessionStorage.setItem(`cards.pos:${storeKey}`, JSON.stringify({ idx, ratings } satisfies Saved))
  }, [idx, ratings, storeKey])

  const go = useCallback((n: number) => { setIdx(Math.max(0, Math.min(total, n))); setFlipped(false) }, [total])

  const patch = (id: number, p: Partial<Card>) => setCards((a) => a.map((c) => (c.id === id ? { ...c, ...p } : c)))
  const refreshCard = async (id: number) => {
    try {
      const updated = (await api.cards({ ids: [id] }))[0]
      if (updated) patch(id, {
        section: updated.section, term: updated.term, term_html: updated.term_html,
        hint: updated.hint, body_html: updated.body_html,
      })
    } catch (e) {
      toast(e instanceof Error ? e.message : '刷新卡片失败', true)
    }
  }
  const send = useCallback(async (id: number, action: Parameters<typeof api.mark>[0]['action']) => {
    try { await api.mark({ target_type: 'card', target_id: id, action }); return true } catch (e) {
      toast(e instanceof Error ? e.message : '操作失败', true)
      return false
    }
  }, [toast])

  const rate = useCallback((action: Rating) => {
    if (!card) return
    setRatings((r) => ({ ...r, [card.id]: action }))
    if (action !== 'rate_hard') patch(card.id, { state: action === 'rate_good' ? 'mastered' : 'again' })
    void send(card.id, action)
    go(idx + 1)
  }, [card, idx, go, send])

  const toggleStar = useCallback(async () => {
    if (!card) return
    const next = !card.starred
    patch(card.id, { starred: next })
    if (!(await send(card.id, next ? 'star' : 'unstar'))) patch(card.id, { starred: !next })
    else toast(next ? '已收藏' : '已取消收藏')
  }, [card, send, toast])

  const addPlan = async () => {
    if (!card) return
    if (await send(card.id, 'plan')) { patch(card.id, { state: 'plan' }); toast('已加入复习') }
  }

  useEffect(() => {
    if (jump || editOpen) return
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.closest('input, textarea, select, [contenteditable="true"]') || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'ArrowLeft') go(idx - 1)
      else if (e.key === 'ArrowRight') go(idx + 1)
      else if (!card) return
      else if (e.key === ' ' && !t.closest('button')) { e.preventDefault(); setFlipped((f) => !f) }
      else if (flipped && ['1', '2', '3'].includes(e.key)) rate(RATES[Number(e.key) - 1].action)
      else if (e.key.toLowerCase() === 's') void toggleStar()
    }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [jump, editOpen, idx, card, flipped, go, rate, toggleStar])

  const onTouchEnd = (e: TouchEvent) => {
    const st = touch.current
    touch.current = null
    if (!st) return
    const dx = e.changedTouches[0].clientX - st.x
    const dy = e.changedTouches[0].clientY - st.y
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) go(idx + (dx < 0 ? 1 : -1))
  }

  return (
    <div className={s.page}>
      <div className={s.top}>
        <Link to="/cards" className={s.back}><Icon name="chevLeft" size={14} /> 返回</Link>
        <span className={s.title}>{queryTitle(query)}</span>
        <Button size="sm" onClick={() => setJump(true)}>{Math.min(idx + 1, total)} / {total} <Icon name="chevDown" size={13} /></Button>
      </div>
      <ProgressBar value={(Math.min(idx, total) / total) * 100} />

      {card ? (
        <>
          <div className={s.stage} onTouchStart={(e) => { touch.current = { x: e.touches[0].clientX, y: e.touches[0].clientY } }} onTouchEnd={onTouchEnd}>
            <CardFace key={`${card.id}-${flipped}`} card={card} flipped={flipped} onFlip={() => setFlipped(true)} />
          </div>
          <div className={s.bar}>
            <div className={s.barInner}>
              {flipped ? RATES.map((r) => (
                <button key={r.action} type="button" className={`${s.rate} ${r.cls} ${ratings[card.id] === r.action ? s.rated : ''}`} onClick={() => rate(r.action)}>
                  {r.label}<kbd>{r.key}</kbd>
                </button>
              )) : <button type="button" className={`${s.rate} ${s.rFlip}`} onClick={() => setFlipped(true)}>翻面<kbd>空格</kbd></button>}
              <button type="button" className={`${s.tool} ${card.starred ? s.toolOn : ''}`} onClick={() => void toggleStar()} aria-pressed={card.starred}><Icon name="star" size={16} fill={card.starred} /><span>收藏</span></button>
              <button type="button" className={`${s.tool} ${card.state === 'plan' ? s.toolOn : ''}`} onClick={() => void addPlan()}><Icon name={card.state === 'plan' ? 'check' : 'plus'} size={16} /><span>{card.state === 'plan' ? '已加入' : '加入复习'}</span></button>
              <button type="button" className={s.tool} onClick={() => setNoteOpen(true)}><Icon name="note" size={16} /><span>笔记</span></button>
              {user?.is_admin && <button type="button" className={s.tool} onClick={() => setEditOpen(true)}><Icon name="edit" size={16} /><span>编辑</span></button>}
              <NoteSheet targetType="card" targetId={card.id} open={noteOpen} onClose={() => setNoteOpen(false)} />
              {user?.is_admin && <AdminCardEditSheet cardId={card.id} open={editOpen} onClose={() => setEditOpen(false)} onSaved={() => { void refreshCard(card.id) }} />}
            </div>
          </div>
          <div className={s.keys}>空格 翻面 · 1/2/3 评分 · S 收藏 · 方向键切换</div>
        </>
      ) : (
        <Summary total={total} ratings={ratings} onRestart={onRestart} onPrev={() => go(total - 1)} />
      )}

      {jump && (
        <Modal title="跳转到题号" onClose={() => setJump(false)} sheet>
          <div className={s.jumpGrid}>
            {cards.map((c, i) => (
              <button key={c.id} type="button" title={c.term}
                className={`${s.jumpItem} ${ratings[c.id] ? s.jumpDone : ''} ${i === idx ? s.jumpCur : ''}`}
                onClick={() => { go(i); setJump(false) }}>{i + 1}</button>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}
