import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { reviewApi, type ReviewDetail, type ReviewQueue, type ReviewStatus } from '@/api/editorial'
import { useAuth } from '@/app/auth'
import { Badge, Button, Card, Field, HtmlView, Input, PageHeader, useToast } from '@/ui'
import { Async } from '../today/Async'
import s from './editorial.module.css'

const categories: Record<string, string> = {
  exact: '完全重复', mechanisms: '中文机制解释', overlap: '内容重叠样例',
  titles: '同标题候选', cross_subject: '跨学科关联', chapters: '章节归类与排版',
}
const statuses: Record<ReviewStatus, string> = {
  pending: '待审核', approved: '认可提案', rejected: '不采纳', needs_revision: '需要修改',
}
const queues: Record<ReviewQueue, string> = {
  needs_review: '待我审核', waiting_execution: '已审核，待处理', completed: '历史已处理', all: '全部记录',
}
const fields: Record<string, string> = {
  subject: '学科', term: '标题', body: '正文', hint: '提示', part: '章节', section: '分节', source_file: '来源',
}
const executionStatuses: Record<string, string> = {
  merged: '已合并', linked: '已双向互引', revised: '已按意见修订', renamed: '已消歧标题',
  deferred: '待核实，原文未改', kept: '保留独立知识点', unchanged: '不采纳，保持原样',
  rolled_back: '已撤销',
}

export default function EditorialPage() {
  const { user } = useAuth()
  return user?.is_admin ? <Workspace /> : <Navigate to="/me" replace />
}

function Workspace() {
  const [sp, setSp] = useSearchParams()
  const requestedQueue = sp.get('queue') ?? ''
  const validQueue = Object.keys(queues).includes(requestedQueue)
  const queue: ReviewQueue = validQueue ? requestedQueue as ReviewQueue : 'needs_review'
  const category = validQueue ? sp.get('category') ?? '' : ''
  const status = validQueue ? sp.get('status') ?? '' : ''
  const query = validQueue ? sp.get('q') ?? '' : ''
  const offset = validQueue ? Math.max(0, Number(sp.get('offset')) || 0) : 0
  const selected = validQueue ? sp.get('item') ?? '' : ''
  const [draft, setDraft] = useState(query)
  const params = { category, status, q: query, offset, queue }
  const list = useQuery({ queryKey: ['editorialList', params], queryFn: () => reviewApi.list(params) })
  const detail = useQuery({
    queryKey: ['editorialDetail', selected], queryFn: () => reviewApi.detail(selected), enabled: !!selected,
  })
  useEffect(() => {
    if (!validQueue) {
      setSp({ queue: 'needs_review' }, { replace: true })
    } else if (queue === 'needs_review' && !selected && !list.isFetching && list.data?.items.length) {
      const next = new URLSearchParams(sp)
      next.set('item', list.data.items[0].id)
      setSp(next, { replace: true })
    }
  }, [validQueue, queue, selected, list.isFetching, list.data, sp, setSp])
  const change = (values: Record<string, string>) => {
    const next = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(values)) { if (v) next.set(k, v); else next.delete(k) }
    setSp(next)
  }
  const saved = (decision: ReviewStatus) => {
    if (queue !== 'needs_review' || decision === 'pending') return
    const items = list.data?.items ?? []
    const index = items.findIndex((item) => item.id === selected)
    const next = index >= 0 ? items[index + 1] ?? items[index - 1] : undefined
    change(next ? { item: next.id } : { item: '', offset: '' })
  }
  const switchQueue = (value: string) => {
    setDraft('')
    setSp({ queue: value })
  }
  return (
    <div className={s.wrap}>
      <PageHeader title={queues[queue]} sub={queue === 'needs_review'
        ? '只显示仍需你确认的内容；已处理项目默认隐藏'
        : queue === 'waiting_execution' ? '已有审核意见，不需要重复审核；等待处理或补充资料'
          : '历史记录仅供查阅，不代表仍需审核'} />
      <Link to="/me/admin">返回管理中心</Link>
      <nav className={s.categories} aria-label="审核工作队列">
        {(['needs_review', 'waiting_execution'] as const).map((key) => <Button key={key}
          variant={queue === key ? 'primary' : 'default'} aria-pressed={queue === key}
          onClick={() => switchQueue(key)}>
          {queues[key]}{list.data ? ` (${list.data.queue_counts[key]})` : ''}
        </Button>)}
      </nav>
      <form className={s.filters} onSubmit={(e) => { e.preventDefault(); change({ q: draft.trim(), offset: '', item: '' }) }}>
        <Input aria-label="搜索审核内容" placeholder="搜索标题或学科" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="submit">搜索</Button>
        {(category || status || query) && <Button type="button" onClick={() => {
          setDraft('')
          change({ category: '', status: '', q: '', offset: '', item: '' })
        }}>清空筛选</Button>}
      </form>
      <details className={s.advanced}>
        <summary>历史记录与高级筛选</summary>
        <div className={s.filters}>
        <select aria-label="工作队列" value={queue} onChange={(e) => switchQueue(e.target.value)}>
          {Object.entries(queues).map(([key, label]) => <option key={key} value={key}>
            {label}{list.data ? ` (${list.data.queue_counts[key as ReviewQueue]})` : ''}
          </option>)}
        </select>
        <select aria-label="审核分类" value={category} onChange={(e) => change({ category: e.target.value, offset: '', item: '' })}>
          <option value="">全部类别</option>
          {Object.entries(categories).map(([key, label]) => <option key={key} value={key}>
            {label}{list.data ? ` (${list.data.counts[key] ?? 0})` : ''}
          </option>)}
        </select>
        <select aria-label="审核状态" value={status} onChange={(e) => change({ status: e.target.value, offset: '', item: '' })}>
          <option value="">全部审核状态</option>
          {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
        </div>
        <p className={s.meta}>保存意见不会执行合并或修改学习内容。已执行但没有单独人工审核记录的项目，不会混入待我审核。</p>
      </details>
      <div className={s.workspace}>
      <aside className={s.queuePanel} aria-label="审核内容列表">
      <Async q={list}>
        {(data) => <>
          <p className={s.meta}>共 {data.total} 项 · 当前第 {Math.floor(offset / 20) + 1} 页</p>
          <div className={s.list}>
            {data.items.map((item) => <button key={item.id} type="button"
              className={`${s.row} ${selected === item.id ? s.selected : ''}`}
              aria-pressed={selected === item.id} onClick={() => change({ item: item.id })}>
              <span>{item.title}</span>
              <span className={s.meta}>{item.subjects.join(' / ')}</span>
              {queue !== 'needs_review' && <Badge tone={item.work_queue === 'completed' ? 'good' : 'warn'}>
                {queues[item.work_queue]}
              </Badge>}
            </button>)}
            {!data.items.length && <p>{category || status || query ? '没有匹配内容，请清空筛选。'
              : queue === 'needs_review' ? '当前没有需要你审核的内容。' : '当前队列没有项目。'}</p>}
          </div>
          <div className={s.actions}>
            <Button disabled={offset === 0} onClick={() => change({ offset: String(Math.max(0, offset - 20)), item: '' })}>上一页</Button>
            <Button disabled={offset + 20 >= data.total} onClick={() => change({ offset: String(offset + 20), item: '' })}>下一页</Button>
          </div>
        </>}
      </Async>
      </aside>
      <section aria-label="审核项目详情" className={s.detail}>
        {selected ?
        <Async q={detail}>
          {(item) => <Detail key={`${item.dataset_id}:${item.id}`} item={item} onSaved={saved} />}
        </Async>
        : <p className={s.meta}>选择一项查看内容。</p>}
      </section>
      </div>
    </div>
  )
}

function Detail({ item, onSaved }: { item: ReviewDetail; onSaved: (status: ReviewStatus) => void }) {
  return <>
    <Card title={item.title}>
      {item.work_queue === 'needs_review' && <p className={s.prose}>{item.decision.note || item.execution?.description || item.guidance}</p>}
      {item.work_queue === 'waiting_execution' && <p>这项已有审核意见，尚未完成处理，不需要重复审核。</p>}
      {item.work_queue === 'completed' && <p>这项已处理，以下内容仅供历史查阅。</p>}
      {item.requires_media_review && <p>涉及图片或媒体，请核对原始图片；图片内容和使用权尚未核实。</p>}
      <details><summary>查看原始审核依据</summary>
        <p className={s.meta}>{item.id}</p>
        <p>{item.guidance}</p>
        {item.differing_fields.length > 0 && <p className={s.meta}>差异字段：{item.differing_fields.map((f) => fields[f] ?? f).join('、')}</p>}
        <p className={s.prose}>{item.evidence}</p>
      </details>
    </Card>
    {item.execution && <details><summary>{item.work_queue === 'needs_review' ? '查看暂缓说明' : '查看执行记录'}</summary><Card title={executionStatuses[item.execution.status] ?? '执行记录'}>
      {item.execution.needs_recheck && <p className={s.warning}>执行后出现了新审核意见，以下结果尚未包含新意见。</p>}
      <p className={s.prose}>{item.execution.description}</p>
      <p className={s.meta}>{new Date(item.execution.created_at).toLocaleString()} · 批次 {item.execution.batch_id}</p>
    </Card></details>}
    {item.cards.length > 0 && <div className={s.compare}>
      {item.cards.map(({ snapshot, current, changed, merged_into }) => (
        <Card key={snapshot.id} title={(current ?? snapshot).term}>
          {merged_into && <p>已并入<Link to={`/cards/run?ids=${merged_into}`}>当前主卡</Link>。</p>}
          {changed && !current && <p className={s.warning}>当前题库中未找到该卡，以下仅为历史快照。</p>}
          <HtmlView html={(current ?? snapshot).term_html} />
          <p className={s.meta}>{(current ?? snapshot).subject} · {(current ?? snapshot).part} · {(current ?? snapshot).section}</p>
          <p className={s.prose}>提示：{(current ?? snapshot).hint || '无'}</p>
          <HtmlView html={(current ?? snapshot).body_html} />
          <details><summary>卡片编号与来源</summary>
            <p className={s.meta}>卡片 {snapshot.id} · {(current ?? snapshot).source_file}</p>
          </details>
          {changed && current && <details>
            <summary>查看 {item.audit_date} 原始快照</summary>
            <p className={s.meta}>当前内容已与此快照不同。</p>
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
      <HtmlView html={item.original_html} />
      <details><summary>查看段落来源</summary><p className={s.meta}>{item.source_file} · 第 {item.line} 行（审计时）</p></details>
      <Link to={`/browse/chapter/${item.chapter_id}`}>查看章节</Link>
    </Card>}
    {item.proposal_html && <details><summary>查看最初审查建议</summary><Card title="最初审查建议（历史原稿）">
      <HtmlView html={item.proposal_html} />
    </Card></details>}
    {item.sources.length > 0 && <details><summary>查看参考来源</summary><Card title="参考来源">
      <ul className={s.sources}>{item.sources.map((source) => <li key={source.url}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
      </li>)}</ul>
      <p className={s.meta}>机制参考不等于最新临床治疗指南；发布前请核对教材与适用边界。</p>
    </Card></details>}
    <Decision key={`${item.id}:${item.decision.version}`} item={item} onSaved={onSaved} />
  </>
}

function Decision({ item, onSaved }: { item: ReviewDetail; onSaved: (status: ReviewStatus) => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [status, setStatus] = useState(item.decision.status)
  const [note, setNote] = useState(item.decision.note)
  const save = useMutation({
    mutationFn: () => reviewApi.save(item.id, { status, note, expected_version: item.decision.version }),
    onSuccess: async (decision) => {
      onSaved(decision.status)
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
      {item.decision.updated_at && <details><summary>查看审核记录时间</summary>
        <p className={s.meta}>{new Date(item.decision.updated_at).toLocaleString()} · 管理员 #{item.decision.updated_by ?? '已注销'}</p>
      </details>}
      <Button type="submit" variant="primary" disabled={save.isPending}>{save.isPending ? '保存中…' : '保存审核意见'}</Button>
    </form>
  </Card>
}
