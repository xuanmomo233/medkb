import { useEffect } from 'react'
import type { QuizMode } from '@/api/types'
import { isTypingTarget, LETTERS } from '../lib'

interface Handlers {
  enabled: boolean
  mode: QuizMode
  optionCount: number
  prev: () => void
  next: () => void
  pick: (letter: string) => void
  confirm: () => void
  reveal: () => void
  star: () => void
}

export function useQuizKeys(h: Handlers) {
  useEffect(() => {
    if (!h.enabled) return
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.ctrlKey || e.metaKey || e.altKey) return
      const k = e.key
      if (k === 'ArrowLeft') h.prev()
      else if (k === 'ArrowRight') h.next()
      else if (k === 'Enter') { if ((e.target as HTMLElement).tagName !== 'BUTTON') h.confirm() }
      else if (k === ' ') {
        if (h.mode !== 'recite') return
        e.preventDefault()
        h.reveal()
      } else if (k === 's' || k === 'S') h.star()
      else {
        const i = /^[1-8]$/.test(k) ? Number(k) - 1 : LETTERS.indexOf(k.toUpperCase())
        if (k.length === 1 && i >= 0 && i < h.optionCount) h.pick(LETTERS[i])
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [h])
}
