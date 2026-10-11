import { useRef, useState } from 'react'
import type { ClipboardEvent, KeyboardEvent } from 'react'
import { Button, Icon, useToast } from '@/ui'
import { MAX_FILE, compressImage, fileToBase64 } from './upload'
import s from './chat.module.css'

export interface Outgoing { message: string; image?: string; file?: { name: string; data: string } }
interface Props { busy: boolean; onSend: (o: Outgoing) => void }

const CHIPS = ['考我一道心衰的题', '帮我梳理呼吸系统重点', '今天该学什么']
const FILE_ACCEPT = '.txt,.md,.csv,.json,.docx,.doc,.pdf'

export default function Composer({ busy, onSend }: Props) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [image, setImage] = useState<string>()
  const [file, setFile] = useState<{ name: string; data: string }>()
  const imgRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const canSend = !busy && (!!text.trim() || !!image || !!file)
  const send = (msg = text) => {
    if (busy || (!msg.trim() && !image && !file)) return
    onSend({ message: msg.trim(), image, file })
    setText(''); setImage(undefined); setFile(undefined)
  }

  const takeImage = async (f: Blob | undefined) => {
    if (!f) return
    try { setImage(await compressImage(f)) } catch (e) { toast(e instanceof Error ? e.message : '图片处理失败', true) }
  }
  const takeFile = async (f: File | undefined) => {
    if (!f) return
    if (f.size > MAX_FILE) { toast('文件不能超过 4MB', true); return }
    try { setFile({ name: f.name, data: await fileToBase64(f) }) } catch (e) { toast(e instanceof Error ? e.message : '文件读取失败', true) }
  }
  const onPaste = (e: ClipboardEvent) => {
    const it = Array.from(e.clipboardData.items).find((i) => i.type.startsWith('image/'))
    if (it) { e.preventDefault(); void takeImage(it.getAsFile() ?? undefined) }
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() }
  }

  return (
    <div className={s.composer}>
      <div className={s.chips}>
        {CHIPS.map((c) => <button key={c} type="button" className={s.chip} disabled={busy} onClick={() => send(c)}>{c}</button>)}
      </div>
      {(image || file) && (
        <div className={s.attach}>
          {image && <div className={s.thumb}><img src={image} alt="待发送图片" /><button type="button" aria-label="移除图片" onClick={() => setImage(undefined)}><Icon name="x" size={12} /></button></div>}
          {file && <div className={s.fileTag}><Icon name="file" size={13} /> {file.name}<button type="button" aria-label="移除文件" onClick={() => setFile(undefined)}><Icon name="x" size={12} /></button></div>}
        </div>
      )}
      <div className={s.inputRow}>
        <Button variant="ghost" size="sm" aria-label="发送图片" title="发送图片" disabled={busy} onClick={() => imgRef.current?.click()}><Icon name="image" size={16} /></Button>
        <Button variant="ghost" size="sm" aria-label="发送文件" title="发送文件" disabled={busy} onClick={() => fileRef.current?.click()}><Icon name="file" size={16} /></Button>
        <textarea className={s.input} rows={1} value={text} placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
          onChange={(e) => setText(e.target.value)} onKeyDown={onKey} onPaste={onPaste} />
        <Button variant="primary" disabled={!canSend} onClick={() => send()}>发送</Button>
      </div>
      <input ref={imgRef} type="file" accept="image/*" hidden onChange={(e) => { void takeImage(e.target.files?.[0]); e.target.value = '' }} />
      <input ref={fileRef} type="file" accept={FILE_ACCEPT} hidden onChange={(e) => { void takeFile(e.target.files?.[0]); e.target.value = '' }} />
    </div>
  )
}
