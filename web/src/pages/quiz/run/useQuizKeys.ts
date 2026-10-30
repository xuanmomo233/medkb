import { useEffect } from 'react'
import type { QuizMode } from '@/api/types'
import { isTypingTarget } from '../lib'
import { optionKey } from '@/optionLabels'

interface Handlers {
  enabled: boolean
  mode: QuizMode
  optionLabels: string[]
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
      } else if ((k === 's' || k === 'S') && !h.optionLabels.includes('S')) h.star()
      else {
        const label = optionKey(k, h.optionLabels)
        if (label) h.pick(label)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [h])
}
