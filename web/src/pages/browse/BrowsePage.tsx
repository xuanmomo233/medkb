import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/endpoints'
import type { ContentTree } from '@/api/types'
import { Badge, EmptyState, ErrorState, Icon, Input, PageHeader, Segmented, Spinner } from '@/ui'
import { useLoad } from './useLoad'
import s from './browse.module.css'

type Tab = 'mindmaps' | 'notes' | 'questions'
interface Item { key: string; label: string; to: string; count?: number }
interface Group { name: string; items: Item[]; sub?: { name: string; items: Item[] }[] }

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
  if (tab === 'questions') {
    return tree.question_tree.map((s) => ({
      name: s.subject_dir,
      items: [],
      sub: s.systems.map((sys) => ({
        name: sys.name,
        items: sys.chapters.map((c) => {
          const label = c.name.startsWith(`${sys.name} · `) ? c.name.slice(sys.name.length + 3) : c.name
          const q = new URLSearchParams({ chapter: c.name, subject_dir: s.subject_dir, system: sys.name })
          return { key: `${s.subject_dir}/${sys.name}/${c.name}`, label, count: c.count, to: `/quiz/run?${q.toString()}` }
        }),
      })),
    }))
  }
  const map = new Map<string, Item[]>()
  const push = (g: string, it: Item) => { const a = map.get(g); if (a) a.push(it); else map.set(g, [it]) }
  for (const c of tree[tab]) push(c.subject, { key: String(c.id), label: c.title, to: `/browse/chapter/${c.id}` })
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
      .map((g) => {
        if (g.name.toLowerCase().includes(k)) return g
        if (g.sub) {
          const sub = g.sub
            .map((sub) => ({ ...sub, items: sub.items.filter((i) => i.label.toLowerCase().includes(k)) }))
            .filter((sub) => sub.items.length > 0 || sub.name.toLowerCase().includes(k))
          return { ...g, sub }
        }
        return { ...g, items: g.items.filter((i) => i.label.toLowerCase().includes(k)) }
      })
      .filter((g) => (g.sub ? g.sub.length > 0 : g.items.length > 0))
  }, [tree, tab, kw])

  return (
    <div>
      <PageHeader title="目录" sub="按学科浏览导图、考点与题库章节" extra={<Link to="/browse/textbooks" className={s.textbooksLink}>整本教材</Link>} />
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
                    <span className={`${s.chev} ${isOpen ? s.chevOpen : ''}`} aria-hidden><Icon name="chevRight" size={13} /></span>
                    <span className={s.groupName}>{g.name}</span>
                    <Badge>{g.sub ? `${g.sub.length} 篇` : `${g.items.length} 章`}</Badge>
                  </button>
                  {isOpen && g.sub && (
                    <div>
                      {g.sub.map((sub) => (
                        <div key={sub.name} className={s.subGroup}>
                          <div className={s.subHead}>{sub.name}</div>
                          <ul className={s.list}>
                            {sub.items.map((i) => (
                              <li key={i.key}>
                                <Link to={i.to} className={s.item}>
                                  <span className={s.itemLabel}>{i.label}</span>
                                  {i.count != null && <span className={s.itemExtra}>{i.count} 题</span>}
                                  <span className={s.go} aria-hidden><Icon name="chevRight" size={13} /></span>
                                </Link>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                  {isOpen && !g.sub && (
                    <ul className={s.list}>
                      {g.items.map((i) => (
                        <li key={i.key}>
                          <Link to={i.to} className={s.item}>
                            <span className={s.itemLabel}>{i.label}</span>
                            {i.count != null && <span className={s.itemExtra}>{i.count} 题</span>}
                            <span className={s.go} aria-hidden><Icon name="chevRight" size={13} /></span>
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
