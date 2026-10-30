import Welcome from './Welcome'
import CheckinCard from './CheckinCard'
import CalendarCard from './CalendarCard'
import TodoCard from './TodoCard'
import ScheduleCard from './ScheduleCard'
import PlanCard from './PlanCard'
import WeakCard from './WeakCard'
import StatsCard from './StatsCard'
import s from './today.module.css'

export default function TodayPage() {
  return (
    <div className={s.page}>
      <Welcome />
      <div className={s.grid}>
        <div className={s.col}>
          <ScheduleCard />
          <PlanCard />
          <TodoCard />
        </div>
        <div className={s.col}>
          <CheckinCard />
          <CalendarCard />
          <WeakCard />
          <StatsCard />
        </div>
      </div>
    </div>
  )
}
