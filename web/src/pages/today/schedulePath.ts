import type { ScheduleItem } from '@/api/types'

export function schedulePath(item: ScheduleItem) {
  return `${item.item_type === 'question' ? '/quiz/run' : '/cards/run'}?ids=${item.item_id}&schedule_item=${item.id}`
}
