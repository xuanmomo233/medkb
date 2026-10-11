import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'
import s from './ui.module.css'

const cx = (...a: (string | false | undefined)[]) => a.filter(Boolean).join(' ')

export { default as HtmlView } from './HtmlView'

// ---------- 按钮 ----------
interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'default' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  block?: boolean
}
export function Button({ variant = 'default', size = 'md', block, className, type = 'button', ...p }: BtnProps) {
  return <button type={type} className={cx(s.btn, s[variant], size !== 'md' && s[size], block && s.block, className)} {...p} />
}

// ---------- 卡片 ----------
interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> { title?: ReactNode; extra?: ReactNode; clickable?: boolean }
export function Card({ title, extra, clickable, className, children, ...p }: CardProps) {
  return (
    <div className={cx(s.card, clickable && s.cardClickable, className)} {...p}>
      {(title || extra) && <div className={s.cardTitle}><span>{title}</span>{extra}</div>}
      {children}
    </div>
  )
}

// ---------- 徽标 ----------
export function Badge({ tone, children }: { tone?: 'brand' | 'good' | 'bad' | 'warn' | 'info'; children: ReactNode }) {
  return <span className={cx(s.badge, tone && s[`b-${tone}`])}>{children}</span>
}

// ---------- 进度条 ----------
export function ProgressBar({ value, tone }: { value: number; tone?: 'good' | 'bad' }) {
  const v = Math.max(0, Math.min(100, value))
  return (
    <div className={s.progress} role="progressbar" aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx(s.progressBar, tone === 'good' && s.progressGood, tone === 'bad' && s.progressBad)} style={{ width: `${v}%` }} />
    </div>
  )
}

// ---------- 状态页 ----------
export function Spinner() { return <div className={s.center}><div className={s.spinner} /></div> }
export function EmptyState({ icon = '📭', text, action }: { icon?: string; text: string; action?: ReactNode }) {
  return <div className={s.center}><div className={s.centerIcon}>{icon}</div><div>{text}</div>{action}</div>
}
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className={s.center}>
      <div className={s.centerIcon}>⚠️</div>
      <div>{error instanceof Error ? error.message : '加载失败'}</div>
      {onRetry && <Button size="sm" onClick={onRetry}>重试</Button>}
    </div>
  )
}

// ---------- 分段选择 ----------
export function Segmented<V extends string>({ value, options, onChange }: {
  value: V; options: { value: V; label: string }[]; onChange: (v: V) => void
}) {
  return (
    <div className={s.segmented} role="tablist">
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" aria-selected={o.value === value}
          className={cx(s.segItem, o.value === value && s.segActive)} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

// ---------- 表单 ----------
export function Field({ label, hint, children }: { label?: string; hint?: string; children: ReactNode }) {
  return <label className={s.field}>{label && <span className={s.label}>{label}</span>}{children}{hint && <span className={s.hint}>{hint}</span>}</label>
}
export function Input(p: InputHTMLAttributes<HTMLInputElement>) { return <input className={cx(s.input, p.className)} {...p} /> }
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className={cx(s.input, p.className)} {...p} /> }

// ---------- 弹层 ----------
export function Modal({ title, onClose, children, sheet }: { title: ReactNode; onClose: () => void; children: ReactNode; sheet?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className={cx(s.overlay, sheet && s.sheet)} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={s.modal} role="dialog" aria-modal="true">
        <div className={s.modalHead}><span>{title}</span><Button variant="ghost" size="sm" onClick={onClose} aria-label="关闭">✕</Button></div>
        <div className={s.modalBody}>{children}</div>
      </div>
    </div>
  )
}

// ---------- 页头 ----------
export function PageHeader({ title, sub, extra }: { title: ReactNode; sub?: ReactNode; extra?: ReactNode }) {
  return <div className={s.pageHead}><div className={s.pageTitle}><h1>{title}</h1>{sub && <span className={s.pageSub}>{sub}</span>}</div>{extra}</div>
}

// ---------- Toast ----------
interface ToastItem { id: number; text: string; error?: boolean }
const ToastCtx = createContext<(text: string, error?: boolean) => void>(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((text: string, error?: boolean) => {
    const id = Date.now() + Math.random()
    setItems((a) => [...a, { id, text, error }])
    setTimeout(() => setItems((a) => a.filter((x) => x.id !== id)), 2600)
  }, [])
  const value = useMemo(() => push, [push])
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className={s.toasts} aria-live="polite">{items.map((t) => <div key={t.id} className={cx(s.toast, t.error && s.toastError)}>{t.text}</div>)}</div>
    </ToastCtx.Provider>
  )
}
