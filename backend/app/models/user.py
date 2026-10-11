from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin


class User(Base, CreatedMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthToken(Base, CreatedMixin):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str] = mapped_column(String(255), default="")


class UserPrefs(Base):
    """每用户一行的强类型设置，替代旧版 settings(k,v) 文本表。"""

    __tablename__ = "user_prefs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    daily_goal: Mapped[int] = mapped_column(Integer, default=30)
    exam_date: Mapped[date | None] = mapped_column(Date)
    plan_start: Mapped[date | None] = mapped_column(Date)
    weak_min_samples: Mapped[int] = mapped_column(Integer, default=10)
    weak_max_rate: Mapped[float] = mapped_column(Float, default=0.6)


class Checkin(Base):
    __tablename__ = "checkins"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InviteCode(Base, CreatedMixin):
    """一次性邀请码，由管理员在后台生成；用后作废。"""

    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SiteConfig(Base):
    """管理员统一维护的站点级配置（k-v）。目前只有 exam_date。"""

    __tablename__ = "site_config"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), default="")
