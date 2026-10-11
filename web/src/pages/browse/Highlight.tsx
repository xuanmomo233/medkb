import type { ReactNode } from 'react'

const esc = (t: string) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const plain = (t: string) => t.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim()

export default function Highlight({ text, q }: { text: string; q: string }): ReactNode {
  const words = q.split(/\s+/).filter(Boolean)
  const t = plain(text)
  if (!words.length) return t
  const parts = t.split(new RegExp(`(${words.map(esc).join('|')})`, 'gi'))
  const set = new Set(words.map((w) => w.toLowerCase()))
  return parts.map((p, i) => (set.has(p.toLowerCase()) ? <mark key={i}>{p}</mark> : p))
}
