import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { ContentTree } from '@/api/types'
import { Badge, EmptyState, ErrorState, Input, PageHeader, Segmented, Spinner } from '@/ui'
import { useLoad } from './useLoad'
import s from './browse.module.css'

type Tab = 'mindmaps' | 'notes' | 'questions'
interface Item { key: string; label: string; to: string; extra?: string }
interface Group { name: string; items: Item[] }

const TABS: { value: Tab; label: string }[] = [
  { value: 'mindmaps', label: '思维导图' },
  { value: 'notes', label: '考点精要' },
  { value: 'questions', label: '题库章节' },
]
const OPEN_KEY = 'browse.open'
const TAB_KEY = 'browse.tab'

function readOpen(): Record<string, boolean> {
  try { return JSON.parse(sessionStorage.getItem(OPEN_KEY) ?? '{}') as Record<string, boolean> } catch { return {} }
}

function group(tree: ContentTree, tab: Tab): Group[] {
  const map = new Map<string, Item[]>()
  const push = (g: string, it: Item) => { const a = map.get(g); if (a) a.push(it); else map.set(g, [it]) }
  if (tab === 'questions') {
    for (const c of tree.question_chapters) {
      const q = new URLSearchParams({ chapter: c.chapter, subject_dir: c.subject_dir, system: c.system })
      push(c.subject_dir, { key: `${c.subject_dir}/${c.system}/${c.chapter}`, label: c.chapter, extra: c.system, to: `/quiz/run?${q.toString()}` })
    }
  } else {
    for (const c of tree[tab]) push(c.subject, { key: String(c.id), label: c.title, to: `/browse/chapter/${c.id}` })
  }
  return [...map].map(([name, items]) => ({ name, items }))
}

const fetchTree = () => api.tree()

export default function BrowsePage() {
  const { data: tree, error, reload } = useLoad(fetchTree)
  const [tab, setTab] = useState<Tab>(() => (sessionStorage.getItem(TAB_KEY) as Tab | null) ?? 'mindmaps')
  const [kw, setKw] = useState('')
  const [open, setOpen] = useState(readOpen)

  const changeTab = (t: Tab) => { setTab(t); sessionStorage.setItem(TAB_KEY, t) }
  const toggle = (id: string, cur: boolean) => {
    const next = { ...open, [id]: !cur }
    setOpen(next)
    sessionStorage.setItem(OPEN_KEY, JSON.stringify(next))
  }

  const groups = useMemo(() => {
    if (!tree) return []
    const k = kw.trim().toLowerCase()
    const all = group(tree, tab)
    if (!k) return all
    return all
      .map((g) => g.name.toLowerCase().includes(k) ? g : { ...g, items: g.items.filter((i) => `${i.label}${i.extra ?? ''}`.toLowerCase().includes(k)) })
      .filter((g) => g.items.length > 0)
  }, [tree, tab, kw])

  return (
    <div>
      <PageHeader title="目录" sub="按学科浏览导图、考点与题库章节" />
      <div className={s.toolbar}>
        <Segmented value={tab} options={TABS} onChange={changeTab} />
        <div className={s.filter}><Input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="在本页过滤学科或章节" aria-label="过滤章节" /></div>
      </div>
      {error ? <ErrorState error={error} onRetry={reload} />
        : !tree ? <Spinner />
        : groups.length === 0 ? <EmptyState text={kw ? '没有匹配的章节' : '暂无内容'} />
        : (
          <div className={s.groups}>
            {groups.map((g) => {
              const id = `${tab}:${g.name}`
              const isOpen = kw.trim() ? true : open[id] ?? false
              return (
                <section key={id} className={s.group}>
                  <button type="button" className={s.groupHead} aria-expanded={isOpen} onClick={() => toggle(id, isOpen)}>
                    <span className={`${s.chev} ${isOpen ? s.chevOpen : ''}`} aria-hidden>›</span>
                    <span className={s.groupName}>{g.name}</span>
                    <Badge>{g.items.length} 章</Badge>
                  </button>
                  {isOpen && (
                    <ul className={s.list}>
                      {g.items.map((i) => (
                        <li key={i.key}>
                          <Link to={i.to} className={s.item}>
                            <span className={s.itemLabel}>{i.label}</span>
                            {i.extra && <span className={s.itemExtra}>{i.extra}</span>}
                            <span className={s.go} aria-hidden>›</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )
            })}
          </div>
        )}
    </div>
  )
}
