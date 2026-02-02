import uuid
from datetime import datetime, date

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram id
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), index=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[str] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    billing_period: Mapped[str] = mapped_column(String(16), nullable=False)  # monthly|yearly
    charge_day: Mapped[int | None] = mapped_column(Integer, nullable=True)   # monthly 1-31
    charge_month: Mapped[int | None] = mapped_column(Integer, nullable=True) # yearly 1-12
    charge_dom: Mapped[int | None] = mapped_column(Integer, nullable=True)   # yearly 1-31

    next_charge_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id"), index=True)

    kind: Mapped[str] = mapped_column(String(4), nullable=False)  # D3 | D1
    charge_date: Mapped[date] = mapped_column(Date, nullable=False)

    remind_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|sending|sent|failed|canceled
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    acked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
