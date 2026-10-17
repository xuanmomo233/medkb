import { Link } from 'react-router-dom'
import type { Card } from '@/api/types'
import { Badge, Citations, HtmlView } from '@/ui'
import s from './run.module.css'
import CardSources from './CardSources'

interface Props { card: Card; flipped: boolean; onFlip: () => void }

export default function CardFace({ card, flipped, onFlip }: Props) {
  if (!flipped) {
    return (
      <div className={`${s.face} ${s.front}`} onClick={onFlip} role="button" tabIndex={0} aria-label="点击翻面"
        onKeyDown={(e) => { if (e.key === 'Enter') onFlip() }}>
        <div className={s.crumb}>{card.subject} · {card.part}{card.section ? ` · ${card.section}` : ''}</div>
        <div className={s.term}>{card.term_html ? <HtmlView html={card.term_html} /> : card.term}</div>
        {card.hint && <div className={s.hint}>{card.hint}</div>}
        <div className={s.flipTip}>点击翻面 · 空格</div>
      </div>
    )
  }
  return (
    <div className={`${s.face} ${s.backFace}`}>
      <div className={s.backHead}>
        {card.term_html
          ? <HtmlView html={card.term_html} className={s.backTerm} />
          : <h2 className={s.backTerm}>{card.term}</h2>}
        <span className={s.backBadges}>
          {card.state === 'mastered' && <Badge tone="good">已掌握</Badge>}
          {card.state === 'again' && <Badge tone="bad">易忘</Badge>}
          {card.starred && <Badge tone="warn">已收藏</Badge>}
        </span>
      </div>
      <HtmlView html={card.body_html} />
      <Citations items={card.citations} />
      <CardSources key={card.id} id={card.id} />
      {!!card.related_cards?.length && <section className={s.srcBox} aria-label="关联知识">
        <h3>关联知识</h3>
        {card.related_cards.map((item) => <p key={item.id}>
          <Link to={`/cards/run?ids=${item.id}`}>{item.subject} · {item.term}</Link>
          <span className={s.crumb}> · {item.reason}</span>
        </p>)}
      </section>}
    </div>
  )
}
