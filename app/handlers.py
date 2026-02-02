import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from sqlalchemy import select, update

from app.config import load_config
from app.db import SessionLocal
from app.models import User, Subscription, Reminder
from app.keyboards import (
    main_menu_kb, currency_kb, period_kb, confirm_kb,
    list_actions_kb, sub_card_kb, how_cancel_kb
)
from app.dates import (
    calc_next_charge_date_monthly, calc_next_charge_date_yearly,
    local_remind_at_days, to_utc, utc_now
)
from app.texts import APPLE_STEPS, GOOGLE_STEPS, WEB_STEPS, UNKNOWN_STEPS

cfg = load_config()

class AddSub(StatesGroup):
    name = State()
    amount = State()
    currency = State()
    currency_other = State()
    period = State()
    monthly_day = State()
    yearly_month = State()
    yearly_day = State()
    confirm = State()

def _period_label(p: str) -> str:
    return "ежемесячно" if p == "monthly" else "раз в год"

async def ensure_user(user_id: int) -> User:
    async with SessionLocal() as s:
        u = await s.get(User, user_id)
        if not u:
            u = User(user_id=user_id, timezone=cfg.default_tz, default_currency=None)
            s.add(u)
            await s.commit()
        return u

async def start_menu(message: Message):
    await ensure_user(message.from_user.id)
    await message.answer("Выбери действие:", reply_markup=main_menu_kb())

async def cb_menu_add(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AddSub.name)
    await cb.message.answer("Как называется сервис? (например: Netflix, iCloud, VPN)")

async def cb_menu_list(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id

    async with SessionLocal() as s:
        subs = (await s.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.deleted_at.is_(None),
            ).order_by(Subscription.created_at.asc())
        )).scalars().all()

    if not subs:
        await cb.message.answer("Пока нет подписок. Добавим первую?", reply_markup=main_menu_kb())
        return

    totals: dict[str, dict[str, Decimal]] = {}
    lines = []
    active_count = 0

    for i, sub in enumerate(subs, 1):
        status = " (выкл. напоминания)" if not sub.is_active else ""
        if sub.is_active:
            active_count += 1

        if sub.billing_period == "monthly":
            date_info = f"{sub.charge_day}"
            per = "мес"
        else:
            date_info = f"{sub.charge_dom:02d}.{sub.charge_month:02d}"
            per = "год"

        lines.append(f"{i}) {sub.name} — {sub.amount} {sub.currency} / {per} ({date_info}){status}")

        cur = sub.currency
        totals.setdefault(cur, {"monthly": Decimal("0"), "yearly": Decimal("0")})

        if sub.is_active:
            if sub.billing_period == "monthly":
                totals[cur]["monthly"] += Decimal(str(sub.amount))
            else:
                totals[cur]["yearly"] += Decimal(str(sub.amount))

    msg = [f"**Активные подписки ({active_count}):**"]
    msg.extend(lines)
    msg.append("\n**Итого (по валютам):**")

    for cur, t in totals.items():
        monthly = t["monthly"]
        yearly = t["yearly"]
        yearly_equiv = (yearly / Decimal("12")) if yearly != 0 else Decimal("0")
        grand_year = monthly * Decimal("12") + yearly
        msg.append(f"- {cur}: {monthly:.2f}/мес + {yearly:.2f}/год (≈ {yearly_equiv:.2f}/мес), в год: {grand_year:.2f}")

    await cb.message.answer("\n".join(msg), reply_markup=list_actions_kb(), parse_mode="Markdown")

async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:128])
    await state.set_state(AddSub.amount)
    await message.answer("Сколько стоит подписка? (например: 9.99)")

async def add_amount(message: Message, state: FSMContext):
    raw = message.text.strip().replace(",", ".")
    try:
        amount = Decimal(raw)
        if amount <= 0:
            raise InvalidOperation
    except Exception:
        await message.answer("Не похоже на сумму. Введи число, например: 9.99")
        return

    await state.update_data(amount=str(amount.quantize(Decimal("0.01"))))
    await state.set_state(AddSub.currency)
    await message.answer("В какой валюте?", reply_markup=currency_kb())

async def cb_currency(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    cur = cb.data.split(":")[-1]
    if cur == "OTHER":
        await state.set_state(AddSub.currency_other)
        await cb.message.answer("Введи валюту (например: GBP)")
        return

    await state.update_data(currency=cur)
    await state.set_state(AddSub.period)
    await cb.message.answer("Как часто списание?", reply_markup=period_kb())

async def add_currency_other(message: Message, state: FSMContext):
    cur = message.text.strip().upper()[:8]
    if not cur.isalpha():
        await message.answer("Введи код валюты буквами, например: GBP")
        return

    await state.update_data(currency=cur)
    await state.set_state(AddSub.period)
    await message.answer("Как часто списание?", reply_markup=period_kb())

async def cb_period(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    per = cb.data.split(":")[-1]
    await state.update_data(period=per)

    if per == "monthly":
        await state.set_state(AddSub.monthly_day)
        await cb.message.answer("Какого числа обычно списание? (1–31)")
    else:
        await state.set_state(AddSub.yearly_month)
        await cb.message.answer("В каком месяце списание? (1–12)")

async def add_monthly_day(message: Message, state: FSMContext):
    try:
        d = int(message.text.strip())
        if d < 1 or d > 31:
            raise ValueError
    except Exception:
        await message.answer("Введи число от 1 до 31.")
        return

    await state.update_data(charge_day=d)
    await state.set_state(AddSub.confirm)
    await show_confirm(message, state)

async def add_yearly_month(message: Message, state: FSMContext):
    try:
        m = int(message.text.strip())
        if m < 1 or m > 12:
            raise ValueError
    except Exception:
        await message.answer("Введи месяц числом 1–12.")
        return

    await state.update_data(charge_month=m)
    await state.set_state(AddSub.yearly_day)
    await message.answer("Какого числа? (1–31)")

async def add_yearly_day(message: Message, state: FSMContext):
    try:
        d = int(message.text.strip())
        if d < 1 or d > 31:
            raise ValueError
    except Exception:
        await message.answer("Введи число от 1 до 31.")
        return

    await state.update_data(charge_dom=d)
    await state.set_state(AddSub.confirm)
    await show_confirm(message, state)

async def show_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    amount = data["amount"]
    currency = data["currency"]
    per = data["period"]

    if per == "monthly":
        date_info = f"{data['charge_day']} числа"
    else:
        date_info = f"{data['charge_dom']:02d}.{data['charge_month']:02d}"

    text = (
        "Проверь:\n"
        f"**{name} — {amount} {currency} — {_period_label(per)} — дата: {date_info}**"
    )
    await message.answer(text, reply_markup=confirm_kb(), parse_mode="Markdown")

async def cb_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    action = cb.data.split(":")[-1]

    if action == "cancel":
        await state.clear()
        await cb.message.answer("Отменено.", reply_markup=main_menu_kb())
        return

    if action == "edit":
        await state.set_state(AddSub.name)
        await cb.message.answer("Ок, начнём заново. Как называется сервис?")
        return

    if action != "save":
        return

    user_id = cb.from_user.id
    u = await ensure_user(user_id)
    data = await state.get_data()

    tz = u.timezone
    now_local = datetime.now(ZoneInfo(tz))

    per = data["period"]
    if per == "monthly":
        next_charge = calc_next_charge_date_monthly(now_local, data["charge_day"])
        billing_period = "monthly"
        charge_day = data["charge_day"]
        charge_month = None
        charge_dom = None
    else:
        next_charge = calc_next_charge_date_yearly(now_local, data["charge_month"], data["charge_dom"])
        billing_period = "yearly"
        charge_day = None
        charge_month = data["charge_month"]
        charge_dom = data["charge_dom"]

    sub = Subscription(
        user_id=user_id,
        name=data["name"],
        amount=data["amount"],
        currency=data["currency"],
        billing_period=billing_period,
        charge_day=charge_day,
        charge_month=charge_month,
        charge_dom=charge_dom,
        next_charge_date=next_charge,
        is_active=True,
        deleted_at=None,
    )

    async with SessionLocal() as s:
        s.add(sub)
        await s.flush()
        await create_reminders(s, sub, tz, next_charge)
        await s.commit()

    await state.clear()
    await cb.message.answer("Сохранено ✅", reply_markup=main_menu_kb())

async def create_reminders(session, sub: Subscription, tz: str, charge_date):
    now_utc = utc_now()

    # Тестовый режим: вместо дней — минуты (чтобы проверить быстро)
    if cfg.test_reminders:
        import datetime as _dt
        for kind, minutes_before in [("D3", cfg.test_d3_minutes), ("D1", cfg.test_d1_minutes)]:
            remind_utc = (now_utc + _dt.timedelta(minutes=max(0, minutes_before))).replace(microsecond=0)
            session.add(Reminder(
                subscription_id=sub.id,
                kind=kind,
                charge_date=charge_date,
                remind_at_utc=remind_utc,
                status="pending",
                attempts=0,
            ))
        return

    # Обычный режим: D-3 и D-1 (в днях)
    for kind, days_before in [("D3", 3), ("D1", 1)]:
        local_dt = local_remind_at_days(charge_date, days_before, cfg.reminder_hour, tz)
        remind_utc = to_utc(local_dt)
        if remind_utc <= now_utc:
            continue

        session.add(Reminder(
            subscription_id=sub.id,
            kind=kind,
            charge_date=charge_date,
            remind_at_utc=remind_utc,
            status="pending",
            attempts=0,
        ))

async def cb_manage(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id

    async with SessionLocal() as s:
        subs = (await s.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.deleted_at.is_(None),
            ).order_by(Subscription.created_at.asc())
        )).scalars().all()

    if not subs:
        await cb.message.answer("Список пуст.", reply_markup=main_menu_kb())
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for sub in subs[:40]:  # MVP лимит
        kb.button(text=sub.name, callback_data=f"sub:open:{sub.id}")
    kb.button(text="↩️ Назад", callback_data="menu:list")
    kb.adjust(1)

    await cb.message.answer("Выбери подписку:", reply_markup=kb.as_markup())

async def cb_sub_open(cb: CallbackQuery):
    await cb.answer()
    sub_id = cb.data.split(":")[-1]

    async with SessionLocal() as s:
        sub = await s.get(Subscription, uuid.UUID(sub_id))
        if not sub or sub.deleted_at is not None or sub.user_id != cb.from_user.id:
            await cb.message.answer("Подписка не найдена.")
            return

    if sub.billing_period == "monthly":
        date_info = f"{sub.charge_day} числа"
        per = "ежемесячно"
    else:
        date_info = f"{sub.charge_dom:02d}.{sub.charge_month:02d}"
        per = "раз в год"

    status = "Активна" if sub.is_active else "Напоминания выключены"

    text = (
        f"**{sub.name}**\n"
        f"Цена: {sub.amount} {sub.currency}\n"
        f"Период: {per}\n"
        f"Дата списания: {date_info}\n"
        f"Статус: {status}"
    )
    await cb.message.answer(text, reply_markup=sub_card_kb(str(sub.id)), parse_mode="Markdown")

async def cb_sub_disable(cb: CallbackQuery):
    await cb.answer()
    sub_id = cb.data.split(":")[-1]

    async with SessionLocal() as s:
        sub = await s.get(Subscription, uuid.UUID(sub_id))
        if not sub or sub.user_id != cb.from_user.id or sub.deleted_at is not None:
            await cb.message.answer("Подписка не найдена.")
            return

        sub.is_active = False
        await s.execute(
            update(Reminder)
            .where(Reminder.subscription_id == sub.id, Reminder.status == "pending")
            .values(status="canceled")
        )
        await s.commit()

    await cb.message.answer("Ок. Напоминания для этой подписки отключены в боте.")

async def cb_sub_delete(cb: CallbackQuery):
    await cb.answer()
    sub_id = cb.data.split(":")[-1]

    async with SessionLocal() as s:
        sub = await s.get(Subscription, uuid.UUID(sub_id))
        if not sub or sub.user_id != cb.from_user.id or sub.deleted_at is not None:
            await cb.message.answer("Подписка не найдена.")
            return

        sub.deleted_at = datetime.utcnow()
        await s.execute(
            update(Reminder)
            .where(Reminder.subscription_id == sub.id, Reminder.status == "pending")
            .values(status="canceled")
        )
        await s.commit()

    await cb.message.answer("Удалено из списка.")

async def cb_sub_how(cb: CallbackQuery):
    await cb.answer()
    sub_id = cb.data.split(":")[-1]
    await cb.message.answer("Где оформлял подписку?", reply_markup=how_cancel_kb(sub_id))

async def cb_cancel_steps(cb: CallbackQuery):
    await cb.answer()
    kind = cb.data.split(":")[1]
    if kind == "apple":
        txt = APPLE_STEPS
    elif kind == "google":
        txt = GOOGLE_STEPS
    elif kind == "web":
        txt = WEB_STEPS
    else:
        txt = UNKNOWN_STEPS
    await cb.message.answer(txt)

async def cb_ok(cb: CallbackQuery):
    # ok:D3:<reminder_id> or ok:D1:<reminder_id>
    await cb.answer()
    _, kind, rid = cb.data.split(":")
    rid_u = uuid.UUID(rid)
    now = datetime.utcnow()

    async with SessionLocal() as s:
        r = await s.get(Reminder, rid_u)
        if not r:
            return

        if r.acked_at is None:
            r.acked_at = now

        # Вариант B: ack D3 -> cancel pending D1 for same charge_date
        if kind == "D3":
            await s.execute(
                update(Reminder)
                .where(
                    Reminder.subscription_id == r.subscription_id,
                    Reminder.charge_date == r.charge_date,
                    Reminder.kind == "D1",
                    Reminder.status == "pending",
                ).values(status="canceled")
            )

        await s.commit()

    await cb.message.answer("Принято ✅")

def setup(dp: Dispatcher):
    dp.message.register(start_menu, F.text.in_({"/start", "/menu"}))
    dp.callback_query.register(cb_menu_add, F.data == "menu:add")
    dp.callback_query.register(cb_menu_list, F.data == "menu:list")

    dp.message.register(add_name, AddSub.name)
    dp.message.register(add_amount, AddSub.amount)

    dp.callback_query.register(cb_currency, F.data.startswith("add:cur:"))
    dp.message.register(add_currency_other, AddSub.currency_other)

    dp.callback_query.register(cb_period, F.data.startswith("add:per:"))
    dp.message.register(add_monthly_day, AddSub.monthly_day)
    dp.message.register(add_yearly_month, AddSub.yearly_month)
    dp.message.register(add_yearly_day, AddSub.yearly_day)

    dp.callback_query.register(cb_confirm, F.data.startswith("add:"))
    dp.callback_query.register(cb_manage, F.data == "subs:manage")

    dp.callback_query.register(cb_sub_open, F.data.startswith("sub:open:"))
    dp.callback_query.register(cb_sub_disable, F.data.startswith("sub:disable:"))
    dp.callback_query.register(cb_sub_delete, F.data.startswith("sub:delete:"))
    dp.callback_query.register(cb_sub_how, F.data.startswith("sub:how:"))

    dp.callback_query.register(cb_cancel_steps, F.data.startswith("cancel:"))
    dp.callback_query.register(cb_ok, F.data.startswith("ok:"))
