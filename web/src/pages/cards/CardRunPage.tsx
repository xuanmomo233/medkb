import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/api/endpoints'
import { useLoad } from '@/pages/browse/useLoad'
import { Button, EmptyState, ErrorState, Spinner } from '@/ui'
import CardRunner from './CardRunner'
import { parseQuery } from './query'
import ScheduleNavigation from '../today/ScheduleNavigation'

export default function CardRunPage() {
  const [params] = useSearchParams()
  const qs = params.toString()
  const query = useMemo(() => parseQuery(new URLSearchParams(qs)), [qs])
  const fetcher = useCallback(() => api.cards(query), [query])
  const { data: cards, error, reload } = useLoad(fetcher)

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!cards) return <Spinner />
  if (cards.length === 0) {
    return <EmptyState icon="cards" text={query.plan_day === undefined ? '这里暂时没有可背的卡片' : '本批计划卡片已完成'} action={<Link to={query.plan_day === undefined ? '/cards' : '/'}><Button variant="primary">返回</Button></Link>} />
  }
  return <><ScheduleNavigation /><CardRunner sessionFresh={Number(params.get('schedule_item')) > 0} key={`${qs}:${cards.map((card) => card.id).join(',')}`} cards={cards} query={query} storeKey={qs} onRestart={() => { sessionStorage.removeItem(`cards.pos:${qs}`); reload() }} /></>
}
