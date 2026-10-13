import { createContext, useCallback, useContext, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'
import { Icon } from './Icon'
import type { IconName } from './Icon'
import s from './ui.module.css'

const cx = (...a: (string | false | undefined)[]) => a.filter(Boolean).join(' ')

export { default as HtmlView } from './HtmlView'
export { Icon } from './Icon'
export type { IconName } from './Icon'

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
export function EmptyState({ icon, text, action }: { icon?: IconName; text: string; action?: ReactNode }) {
  return <div className={s.center}>{icon && <div className={s.centerIcon}><Icon name={icon} size={40} /></div>}<div>{text}</div>{action}</div>
}
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className={s.center}>
      <div className={s.centerIcon}><Icon name="flag" size={40} /></div>
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
export function Modal({ title, onClose, children, sheet, side }: { title: ReactNode; onClose: () => void; children: ReactNode; sheet?: boolean; side?: boolean }) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  const titleId = useId()

  useLayoutEffect(() => { closeRef.current = onClose }, [onClose])
  useLayoutEffect(() => {
    const overlay = overlayRef.current!
    const dialog = dialogRef.current!
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    const background = Array.from(document.body.children)
      .filter((element): element is HTMLElement => element instanceof HTMLElement && element !== overlay)
      .map((element) => ({ element, inert: element.inert }))
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, [tabindex], [contenteditable="true"]',
    )).filter((element) =>
      element.tabIndex >= 0 && !element.matches(':disabled') &&
      !element.closest('[inert]') && element.getClientRects().length > 0,
    )
    const focusFirst = () => (focusable()[0] ?? dialog).focus()

    background.forEach(({ element }) => { element.inert = true })
    document.body.style.overflow = 'hidden'
    focusFirst()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (overlay.inert || event.defaultPrevented) return
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current()
      } else if (event.key === 'Tab') {
        const elements = focusable()
        const first = elements[0]
        const last = elements.at(-1)
        const active = document.activeElement
        if (!first || !dialog.contains(active) || active === dialog ||
          (!event.shiftKey && active === last) || (event.shiftKey && active === first)) {
          event.preventDefault()
          const target = event.shiftKey ? last ?? dialog : first ?? dialog
          target.focus()
        }
      }
    }
    const handleFocus = (event: FocusEvent) => {
      if (!overlay.inert && event.target instanceof Node && !dialog.contains(event.target)) focusFirst()
    }
    const observer = new MutationObserver(() => {
      if (!overlay.inert && !dialog.contains(document.activeElement)) focusFirst()
    })
    observer.observe(dialog, {
      childList: true, subtree: true, attributes: true,
      attributeFilter: ['disabled', 'hidden', 'tabindex', 'class', 'style'],
    })
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('focusin', handleFocus)
    return () => {
      observer.disconnect()
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('focusin', handleFocus)
      background.forEach(({ element, inert }) => { element.inert = inert })
      document.body.style.overflow = previousOverflow
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true })
    }
  }, [])

  return createPortal(
    <div ref={overlayRef} className={cx(s.overlay, sheet && s.sheet, side && s.side)} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={dialogRef} className={cx(s.modal, side && s.modalSide)} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <div className={s.modalHead}><span id={titleId}>{title}</span><Button variant="ghost" size="sm" onClick={onClose} aria-label="关闭"><Icon name="x" /></Button></div>
        <div className={s.modalBody}>{children}</div>
      </div>
    </div>, document.body,
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
