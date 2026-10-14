import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { reviewApi, type ReviewDetail, type ReviewStatus } from '@/api/editorial'
import { useAuth } from '@/app/auth'
import { Badge, Button, Card, Field, HtmlView, Input, PageHeader, useToast } from '@/ui'
import { Async } from '../today/Async'
import s from './editorial.module.css'

const categories: Record<string, string> = {
  exact: '完全重复', mechanisms: '中文机制解释', overlap: '内容重叠样例',
  titles: '同标题候选', cross_subject: '跨学科关联', chapters: '章节归类与排版',
}
const statuses: Record<ReviewStatus, string> = {
  pending: '待审核', approved: '认可提案（未执行）', rejected: '不采纳', needs_revision: '需要修改',
}
const fields: Record<string, string> = {
  subject: '学科', term: '标题', body: '正文', hint: '提示', part: '章节', section: '分节', source_file: '来源',
}

export default function EditorialPage() {
  const { user } = useAuth()
  return user?.is_admin ? <Workspace /> : <Navigate to="/me" replace />
}

function Workspace() {
  const [sp, setSp] = useSearchParams()
  const category = sp.get('category') ?? 'exact'
  const status = sp.get('status') ?? ''
  const query = sp.get('q') ?? ''
  const offset = Math.max(0, Number(sp.get('offset')) || 0)
  const selected = sp.get('item') ?? ''
  const [draft, setDraft] = useState(query)
  const params = { category, status, q: query, offset }
  const list = useQuery({ queryKey: ['editorialList', params], queryFn: () => reviewApi.list(params) })
  const detail = useQuery({
    queryKey: ['editorialDetail', selected], queryFn: () => reviewApi.detail(selected), enabled: !!selected,
  })
  const change = (values: Record<string, string>) => {
    const next = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(values)) { if (v) next.set(k, v); else next.delete(k) }
    setSp(next)
  }
  return (
    <div className={s.wrap}>
      <PageHeader title="内容审核" sub="管理员专用 · 提案与原内容对比" />
      <Link to="/me/admin">返回管理中心</Link>
      <div className={s.notice}>
        <strong>审核与执行分离</strong>
        <p>此处保存的只是审核状态和意见。认可提案也不会合并、删除、覆盖卡片或修改学习进度。</p>
        <p>原始快照来自 {list.data?.audit_date ?? '内容审计'}。同标题不等于重复；语义重叠仅抽查样例，中文机制解释仍需按教材复核。</p>
      </div>
      <nav className={s.categories} aria-label="审核分类">
        {Object.entries(categories).map(([key, label]) => (
          <Button key={key} size="sm" variant={category === key ? 'primary' : 'default'}
            aria-pressed={category === key} onClick={() => change({ category: key, offset: '', item: '' })}>
            {label}{list.data ? ` (${list.data.counts[key] ?? 0})` : ''}
          </Button>
        ))}
      </nav>
      <form className={s.filters} onSubmit={(e) => { e.preventDefault(); change({ q: draft.trim(), offset: '', item: '' }) }}>
        <Input aria-label="搜索标题、学科、卡片 ID 或审核编号" placeholder="标题 / 学科 / 卡片 ID / 编号" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <select aria-label="审核状态" value={status} onChange={(e) => change({ status: e.target.value, offset: '', item: '' })}>
          <option value="">全部状态</option>
          {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
        <Button type="submit">搜索</Button>
      </form>
      <Async q={list}>
        {(data) => <>
          <p className={s.meta}>共 {data.total} 项 · 当前第 {Math.floor(offset / 20) + 1} 页</p>
          <div className={s.list}>
            {data.items.map((item) => <button key={item.id} type="button"
              className={`${s.row} ${selected === item.id ? s.selected : ''}`}
              aria-pressed={selected === item.id} onClick={() => change({ item: item.id })}>
              <span>{item.id} · {item.title}</span>
              <span className={s.meta}>{item.subjects.join(' / ')}{item.card_ids.length > 0 && ` · 卡片 ${item.card_ids.join('、')}`}</span>
              <Badge tone={item.decision.status === 'approved' ? 'good' : 'warn'}>{statuses[item.decision.status]}</Badge>
            </button>)}
            {!data.items.length && <p>没有匹配的审核项目。</p>}
          </div>
          <div className={s.actions}>
            <Button disabled={offset === 0} onClick={() => change({ offset: String(Math.max(0, offset - 20)), item: '' })}>上一页</Button>
            <Button disabled={offset + 20 >= data.total} onClick={() => change({ offset: String(offset + 20), item: '' })}>下一页</Button>
          </div>
        </>}
      </Async>
      {selected && <section aria-label="审核项目详情" className={s.detail}>
        <Async q={detail}>
          {(item) => <Detail key={`${item.dataset_id}:${item.id}`} item={item} />}
        </Async>
      </section>}
    </div>
  )
}

function Detail({ item }: { item: ReviewDetail }) {
  return <>
    <Card title={`${item.id} · ${item.title}`}>
      <p>{item.guidance}</p>
      {item.differing_fields.length > 0 && <p className={s.meta}>差异字段：{item.differing_fields.map((f) => fields[f] ?? f).join('、')}</p>}
      {item.requires_media_review && <p>涉及图片或媒体，请核对原始图片；图片内容和使用权尚未核实。</p>}
      <details><summary>详细审核依据与保留要求（原稿）</summary><p className={s.prose}>{item.evidence}</p></details>
    </Card>
    {item.cards.length > 0 && <div className={s.compare}>
      {item.cards.map(({ snapshot, current, changed }) => (
        <Card key={snapshot.id} title={`原卡 #${snapshot.id}`}>
          {changed && <p className={s.warning}>{current ? '当前卡已与审计快照不同，请同时核对。' : '当前题库中未找到该卡，以下仅为审计快照。'}</p>}
          <HtmlView html={(current ?? snapshot).term_html} />
          <p className={s.meta}>{(current ?? snapshot).subject} · {(current ?? snapshot).part} · {(current ?? snapshot).section}</p>
          <p className={s.prose}>提示：{(current ?? snapshot).hint || '无'}</p>
          <HtmlView html={(current ?? snapshot).body_html} />
          <p className={s.meta}>来源：{(current ?? snapshot).source_file}</p>
          {changed && current && <details>
            <summary>查看 {item.audit_date} 原始快照</summary>
            <HtmlView html={snapshot.term_html} />
            <p>提示：{snapshot.hint || '无'}</p>
            <HtmlView html={snapshot.body_html} />
            <p className={s.meta}>{snapshot.source_file}</p>
          </details>}
          <details><summary>查看原始 Markdown</summary><pre className={s.raw}>{(current ?? snapshot).body}</pre></details>
          {current && <Link to={`/cards/run?ids=${current.id}`}>在背卡中查看</Link>}
        </Card>
      ))}
    </div>}
    {item.original_html && <Card title="原章节段落">
      <p className={s.meta}>{item.source_file} · 第 {item.line} 行（审计时）</p>
      <HtmlView html={item.original_html} />
      <Link to={`/browse/chapter/${item.chapter_id}`}>查看章节</Link>
    </Card>}
    {item.proposal_html && <Card title="建议内容 · 尚未发布"><HtmlView html={item.proposal_html} /></Card>}
    {item.sources.length > 0 && <Card title="参考来源">
      <ul className={s.sources}>{item.sources.map((source) => <li key={source.url}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
      </li>)}</ul>
      <p className={s.meta}>机制参考不等于最新临床治疗指南；发布前请核对教材与适用边界。</p>
    </Card>}
    <Decision key={`${item.id}:${item.decision.version}`} item={item} />
  </>
}

function Decision({ item }: { item: ReviewDetail }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [status, setStatus] = useState(item.decision.status)
  const [note, setNote] = useState(item.decision.note)
  const save = useMutation({
    mutationFn: () => reviewApi.save(item.id, { status, note, expected_version: item.decision.version }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['editorialList'] }),
        qc.invalidateQueries({ queryKey: ['editorialDetail', item.id] }),
      ])
      toast('审核意见已保存；没有修改原卡或章节')
    },
    onError: (e: Error) => toast(e.message, true),
  })
  return <Card title="记录审核意见">
    <form className={s.decision} onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
      <Field label="审核状态">
        <select value={status} onChange={(e) => setStatus(e.target.value as ReviewStatus)}>
          {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </Field>
      <Field label="意见 / 需要保留的内容 / 修改要求">
        <textarea value={note} maxLength={4000} rows={5} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <p className={s.meta}>状态保存后可重新修改。“认可提案”只认可方案，不执行合并、删除或内容替换。</p>
      {item.decision.updated_at && <p className={s.meta}>最近记录：{new Date(item.decision.updated_at).toLocaleString()} · 管理员 #{item.decision.updated_by ?? '已注销'}</p>}
      <Button type="submit" variant="primary" disabled={save.isPending}>{save.isPending ? '保存中…' : '保存审核意见'}</Button>
    </form>
  </Card>
}
