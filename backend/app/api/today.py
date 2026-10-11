from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, Session
from app.schemas import today as s
from app.services import study as svc

router = APIRouter()


@router.get("/today", response_model=s.TodaySummary)
async def today(user: CurrentUser, session: Session):
    return await svc.today_summary(session, user)


@router.post("/checkin", response_model=s.CheckinOut)
async def checkin(user: CurrentUser, session: Session):
    return {"streak": await svc.do_checkin(session, user.id)}


@router.get("/calendar", response_model=s.CalendarMonth)
async def calendar(user: CurrentUser, session: Session, month: Annotated[str, Query()]):
    return await svc.calendar_month(session, user.id, month)


@router.get("/prefs", response_model=s.PrefsOut)
async def get_prefs(user: CurrentUser, session: Session):
    return await svc.get_prefs(session, user.id)


@router.put("/prefs", response_model=s.PrefsOut)
async def put_prefs(body: s.PrefsUpdate, user: CurrentUser, session: Session):
    data = {k: getattr(body, k) for k in body.model_fields_set}
    return await svc.update_prefs(session, user.id, data)


@router.get("/plan", response_model=s.PlanToday)
async def plan(user: CurrentUser, session: Session):
    return await svc.plan_today(session, user.id)


@router.get("/plan/days/{n}", response_model=s.PlanDayDetail)
async def plan_day(n: int, user: CurrentUser, session: Session):
    return await svc.plan_day_detail(session, n)


@router.post("/plan/restart", status_code=204)
async def plan_restart(user: CurrentUser, session: Session):
    await svc.plan_restart(session, user.id)
    return Response(status_code=204)


@router.get("/stats/overview", response_model=s.StatsOverview)
async def stats_overview(user: CurrentUser, session: Session):
    return await svc.stats_overview(session, user.id)


@router.get("/stats/weakspots", response_model=list[s.WeakSpot])
async def weakspots(user: CurrentUser, session: Session):
    return await svc.weak_spots(session, user.id)


@router.get("/schedule/today", response_model=s.ScheduleToday)
async def schedule_today(user: CurrentUser, session: Session):
    return await svc.schedule_today(session, user.id)


@router.post("/schedule/items/{item_id}/done", status_code=204)
async def schedule_done(item_id: int, user: CurrentUser, session: Session):
    await svc.schedule_done(session, user.id, item_id)
    return Response(status_code=204)
