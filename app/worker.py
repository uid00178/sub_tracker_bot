import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import text, select, update

from app.config import load_config
from app.db import SessionLocal
from app.models import Reminder, Subscription, User
from app.texts import reminder_text
from app.keyboards import ok_kb
from app.dates import (
    utc_now, calc_next_charge_date_monthly, calc_next_charge_date_yearly,
    local_remind_at_days, to_utc
)

cfg = load_config()

BATCH = 50
SLEEP_SECONDS = 3

async def rollover_subscriptions():
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(Subscription, User).join(User, User.user_id == Subscription.user_id)
            .where(
                Subscription.deleted_at.is_(None),
                Subscription.is_active.is_(True),
            )
        )).all()

        now_utc = utc_now()

        for sub, u in rows:
            tz = u.timezone or cfg.default_tz
            now_local = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(tz))

            # если next_charge_date уже в прошлом, двигаем вперёд
            if sub.next_charge_date >= now_local.date():
                continue

            if sub.billing_period == "monthly":
                next_charge = calc_next_charge_date_monthly(now_local, sub.charge_day)
            else:
                next_charge = calc_next_charge_date_yearly(now_local, sub.charge_month, sub.charge_dom)

            sub.next_charge_date = next_charge

            # создаём reminders для нового charge_date (если ещё нет)
            if cfg.test_reminders:
                # В тестовом режиме не плодим rollover reminders бесконечно
                # (иначе ты утонешь в тестовых уведомлениях)
                continue

            for kind, days_before in [("D3", 3), ("D1", 1)]:
                local_dt = local_remind_at_days(next_charge, days_before, cfg.reminder_hour, tz)
                remind_utc = to_utc(local_dt)
                if remind_utc <= now_utc:
                    continue

                exists = (await s.execute(
                    select(Reminder.id).where(
                        Reminder.subscription_id == sub.id,
                        Reminder.charge_date == next_charge,
                        Reminder.kind == kind,
                        Reminder.status.in_(("pending", "sending", "sent")),
                    )
                )).first()

                if exists:
                    continue

                s.add(Reminder(
                    subscription_id=sub.id,
                    kind=kind,
                    charge_date=next_charge,
                    remind_at_utc=remind_utc,
                    status="pending",
                    attempts=0,
                ))

        await s.commit()

async def fetch_due_reminders():
    sql = text("""
        WITH picked AS (
          SELECT id
          FROM reminders
          WHERE status = 'pending' AND remind_at_utc <= NOW()
          ORDER BY remind_at_utc
          LIMIT :limit
          FOR UPDATE SKIP LOCKED
        )
        UPDATE reminders
        SET status = 'sending'
        WHERE id IN (SELECT id FROM picked)
        RETURNING id;
    """)
    async with SessionLocal() as s:
        rows = (await s.execute(sql, {"limit": BATCH})).all()
        await s.commit()
    return [r[0] for r in rows]

async def send_one(bot: Bot, reminder_id):
    async with SessionLocal() as s:
        r = await s.get(Reminder, reminder_id)
        if not r or r.status != "sending":
            return

        sub = await s.get(Subscription, r.subscription_id)
        if not sub or sub.deleted_at is not None or not sub.is_active:
            r.status = "canceled"
            await s.commit()
            return

        # Вариант B: перед отправкой D1 проверяем, не acked ли D3
        if r.kind == "D1":
            d3 = (await s.execute(
                select(Reminder).where(
                    Reminder.subscription_id == r.subscription_id,
                    Reminder.charge_date == r.charge_date,
                    Reminder.kind == "D3",
                )
            )).scalars().first()

            if d3 and d3.acked_at is not None:
                r.status = "canceled"
                await s.commit()
                return

        text_msg = reminder_text(r.kind, sub.name, str(sub.amount), sub.currency, r.charge_date)

        try:
            await bot.send_message(
                chat_id=sub.user_id,
                text=text_msg,
                reply_markup=ok_kb(r.kind, str(r.id)),
                parse_mode="Markdown",
            )
            r.status = "sent"
            await s.commit()
        except Exception as e:
            r.status = "failed"
            r.attempts += 1
            r.last_error = str(e)[:800]
            await s.commit()

async def loop():
    bot = Bot(token=cfg.bot_token)

    last_rollover = 0.0
    while True:
        now = asyncio.get_event_loop().time()

        # rollover раз в 10 минут
        if now - last_rollover > 600:
            try:
                await rollover_subscriptions()
            except Exception:
                pass
            last_rollover = now

        ids = await fetch_due_reminders()
        if not ids:
            await asyncio.sleep(SLEEP_SECONDS)
            continue

        for rid in ids:
            await send_one(bot, rid)

async def main():
    await loop()

if __name__ == "__main__":
    asyncio.run(main())
