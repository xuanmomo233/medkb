import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useLoad } from '@/pages/browse/useLoad'
import { Button, EmptyState, ErrorState, Spinner } from '@/ui'
import CardRunner from './CardRunner'
import { parseQuery } from './query'
import { useScheduleNavigation } from '../today/useScheduleNavigation'

export default function CardRunPage() {
  const [params] = useSearchParams()
  const qs = params.toString()
  const schedule = useScheduleNavigation()
  const scheduledCardId = schedule.active ? schedule.items[schedule.index]?.item_id : undefined
  const query = useMemo(() => {
    const parsed = parseQuery(new URLSearchParams(qs))
    if (scheduledCardId) parsed.ids = [scheduledCardId]
    return parsed
  }, [qs, scheduledCardId])
  const fetcher = useCallback(() => api.cards(query), [query])
  const { data: cards, error, reload } = useLoad(fetcher)

  if (schedule.error) return <ErrorState error={schedule.error} onRetry={schedule.reload} />
  if (schedule.pending) return <Spinner />
  if (schedule.active && schedule.index < 0) return <EmptyState text="这份日程已更新，请返回今日重新进入" action={<Link to="/"><Button>返回今日</Button></Link>} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!cards) return <Spinner />
  if (cards.length === 0) {
    return <EmptyState icon="cards" text={query.plan_day === undefined ? '这里暂时没有可背的卡片' : '本批计划卡片已完成'} action={<Link to={query.plan_day === undefined ? '/cards' : '/'}><Button variant="primary">返回</Button></Link>} />
  }
  const storeKey = schedule.active ? `schedule:${schedule.scope}:card:${cards.map((card) => card.id).join(',')}` : qs
  return <CardRunner schedule={schedule.active ? schedule : undefined} key={`${qs}:${cards.map((card) => card.id).join(',')}`} cards={cards} query={query} storeKey={storeKey} onRestart={() => { sessionStorage.removeItem(`cards.pos:${storeKey}`); reload() }} />
}
