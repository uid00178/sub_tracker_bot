from datetime import date

def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")

def reminder_text(kind: str, name: str, amount: str, currency: str, charge_date: date) -> str:
    when = "Через 3 дня" if kind == "D3" else "Завтра"
    return (
        f"{when} списание: **{name} — {amount} {currency}**\n"
        f"Дата: **{fmt_date(charge_date)}**\n\n"
        "Бот напоминает о списании. Отменить подписку можно только в самом сервисе."
    )

APPLE_STEPS = (
    "Как отменить подписку через Apple ID:\n"
    "1) Открой Настройки на iPhone/iPad\n"
    "2) Нажми на своё имя (Apple ID)\n"
    "3) Подписки (Subscriptions)\n"
    "4) Выбери сервис и нажми Отменить\n"
)

GOOGLE_STEPS = (
    "Как отменить подписку через Google Play:\n"
    "1) Открой Google Play\n"
    "2) Профиль → Платежи и подписки\n"
    "3) Подписки\n"
    "4) Выбери сервис и нажми Отменить\n"
)

WEB_STEPS = (
    "Как отменить подписку на сайте сервиса:\n"
    "1) Зайди в аккаунт сервиса\n"
    "2) Открой Billing / Payments / Subscription\n"
    "3) Отмени автопродление\n"
    "4) Проверь, что статус изменился\n"
)

UNKNOWN_STEPS = (
    "Если не помнишь, где оформлял:\n"
    "1) Проверь Apple/Google подписки\n"
    "2) Найди письмо с чеком/подтверждением\n"
    "3) В выписке банка найди мерчанта и отменяй там\n"
)
