import type { Question } from '@/api/types'
import { Button, Icon } from '@/ui'
import type { IconName } from '@/ui'
import type { MarkKind } from './useQuizSession'
import s from './run.module.css'

interface Props {
  q: Question
  canRedo: boolean
  onToggle: (k: MarkKind) => void
  onRedo: () => void
}

export default function QuestionToolbar({ q, canRedo, onToggle, onRedo }: Props) {
  const items: { kind: MarkKind; on: boolean; label: string; onLabel: string; icon: IconName; title: string }[] = [
    { kind: 'star', on: q.starred, label: '收藏', onLabel: '已收藏', icon: 'star', title: '收藏（S）' },
    { kind: 'wrong', on: q.state === 'again', label: '错题本', onLabel: '已加入错题本', icon: 'x', title: '加入/移出错题本' },
    { kind: 'master', on: q.state === 'mastered', label: '掌握', onLabel: '已掌握', icon: 'check', title: '标记完全掌握' },
    { kind: 'plan', on: q.state === 'plan', label: '复习计划', onLabel: '已在计划', icon: 'plus', title: '加入/移出复习计划' },
  ]
  return (
    <div className={s.toolbar}>
      {items.map((it) => (
        <Button key={it.kind} size="sm" variant={it.on ? 'primary' : 'default'} aria-pressed={it.on} title={it.title}
          onClick={() => onToggle(it.kind)}>
          <Icon name={it.icon} size={14} fill={it.on && it.kind === 'star'} />{it.on ? it.onLabel : it.label}
        </Button>
      ))}
      {canRedo && <Button size="sm" variant="ghost" onClick={onRedo}><Icon name="redo" size={14} /> 重做</Button>}
    </div>
  )
}
