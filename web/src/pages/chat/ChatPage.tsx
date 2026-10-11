import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { ChatQuiz, ChatSendBody } from '@/api/types'
import { Button, EmptyState, ErrorState, HtmlView, Modal, Spinner, useToast } from '@/ui'
import Composer from './Composer'
import type { Outgoing } from './Composer'
import QuizCard from './QuizCard'
import s from './chat.module.css'

type Item =
  | { id: number; kind: 'text'; role: 'user' | 'assistant'; text: string; html: string; image?: string; fileName?: string }
  | { id: number; kind: 'quiz'; quiz: ChatQuiz }

let seq = 0
const nid = () => ++seq

export default function ChatPage() {
  const toast = useToast()
  const [params] = useSearchParams()
  const ctx = params.get('ctx') ?? undefined
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [loadErr, setLoadErr] = useState<unknown>(null)
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState<{ body: ChatSendBody; msg: string } | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    api.chatHistory()
      .then((h) => setItems(h.map((m) => ({ id: nid(), kind: 'text', role: m.role, text: m.content, html: m.html }))))
      .then(() => setLoadErr(null), setLoadErr)
      .finally(() => setLoading(false))
  }, [])
  useEffect(load, [load])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [items, pending, failed])

  const push = (...a: Item[]) => setItems((o) => [...o, ...a])

  const request = async (body: ChatSendBody) => {
    setPending(true); setFailed(null)
    try {
      const r = await api.chatSend(body)
      push({ id: nid(), kind: 'text', role: 'assistant', text: r.reply, html: r.reply_html },
        ...r.quizzes.map((quiz): Item => ({ id: nid(), kind: 'quiz', quiz })))
    } catch (e) {
      setFailed({ body, msg: e instanceof Error ? e.message : '发送失败' })
    } finally { setPending(false) }
  }

  const send = (o: Outgoing) => {
    const body: ChatSendBody = { message: o.message || (o.image ? '请看这张图片' : '请看这个文件'), context: ctx, image: o.image, file: o.file }
    push({ id: nid(), kind: 'text', role: 'user', text: o.message, html: '', image: o.image, fileName: o.file?.name })
    void request(body)
  }

  const clear = async () => {
    try { await api.chatClear(); setItems([]); setFailed(null); setConfirmClear(false); toast('已清空记录') }
    catch (e) { toast(e instanceof Error ? e.message : '清空失败', true) }
  }

  return (
    <div className={s.page}>
      <div className={s.head}>
        <div className={s.title}>🤖 AI 陪学{ctx && <span className={s.ctx}>已带入上下文</span>}</div>
        <Button variant="ghost" size="sm" disabled={!items.length || pending} onClick={() => setConfirmClear(true)}>清空记录</Button>
      </div>
      <div className={s.scroll}>
        {loading ? <Spinner /> : loadErr ? <ErrorState error={loadErr} onRetry={() => { setLoading(true); load() }} /> : (
          <div className={s.list}>
            {!items.length && !pending && <EmptyState icon="💬" text="你好！我是你的 AI 陪学，可以提问、让我出题或发图片/文件。" />}
            {items.map((m) => m.kind === 'quiz' ? (
              <div key={m.id} className={`${s.row} ${s.left}`}>
                <QuizCard quiz={m.quiz} onResult={(r) => push({ id: nid(), kind: 'text', role: 'assistant', text: r.reply, html: r.reply_html })} />
              </div>
            ) : m.role === 'user' ? (
              <div key={m.id} className={`${s.row} ${s.right}`}>
                <div className={`${s.bubble} ${s.user}`}>
                  {m.image && <img className={s.pic} src={m.image} alt="发送的图片" />}
                  {m.fileName && <div className={s.fileLine}>📄 {m.fileName}</div>}
                  {m.text && <div className={s.plain}>{m.text}</div>}
                </div>
              </div>
            ) : (
              <div key={m.id} className={`${s.row} ${s.left}`}>
                <div className={`${s.bubble} ${s.bot}`}><HtmlView html={m.html || m.text} /></div>
              </div>
            ))}
            {pending && <div className={`${s.row} ${s.left}`}><div className={`${s.bubble} ${s.bot} ${s.thinking}`}>思考中…</div></div>}
            {failed && (
              <div className={`${s.row} ${s.left}`}>
                <div className={`${s.bubble} ${s.err}`}>
                  <span>{failed.msg}</span>
                  <Button size="sm" onClick={() => void request(failed.body)}>重试</Button>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>
      <Composer busy={pending} onSend={send} />
      {confirmClear && (
        <Modal title="清空聊天记录" onClose={() => setConfirmClear(false)}>
          <p style={{ marginBottom: 16 }}>清空后无法恢复，确定继续吗？</p>
          <div className={s.dialogActions}>
            <Button onClick={() => setConfirmClear(false)}>取消</Button>
            <Button variant="danger" onClick={clear}>清空</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}

