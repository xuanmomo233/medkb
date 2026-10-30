import { Icon, Modal } from '@/ui'
import type { ScheduleNavigationState } from './useScheduleNavigation'
import s from './scheduleNavigation.module.css'

export default function ScheduleJumpGrid({ navigation, onClose }: {
  navigation: ScheduleNavigationState
  onClose: () => void
}) {
  const { items, index, go } = navigation
  return <Modal title="题号跳转" onClose={onClose} sheet>
    <p className={s.hint}>已完成 {items.filter((item) => item.done).length} / {items.length} · 点击题号可自由切换</p>
    <div className={s.grid}>
      {items.map((item, i) => <button key={item.id} type="button"
        className={`${s.cell} ${item.done ? s.done : ''} ${i === index ? s.current : ''}`}
        title={item.title} aria-current={i === index ? 'step' : undefined}
        aria-label={`第 ${i + 1} 题，${item.item_type === 'question' ? '题目' : '卡片'}，${item.done ? '已完成' : '未完成'}：${item.title}`}
        onClick={() => { go(i); onClose() }}>
        <strong>{i + 1}</strong><span>{item.item_type === 'question' ? '题目' : '卡片'}</span>
        {item.done && <Icon name="check" size={11} className={s.mark} />}
      </button>)}
    </div>
  </Modal>
}
