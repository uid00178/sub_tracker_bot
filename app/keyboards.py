from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить подписку", callback_data="menu:add")
    kb.button(text="📋 Все мои подписки", callback_data="menu:list")
    kb.adjust(1)
    return kb.as_markup()

def currency_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in ["EUR", "USD", "RUB"]:
        kb.button(text=c, callback_data=f"add:cur:{c}")
    kb.button(text="Другая", callback_data="add:cur:OTHER")
    kb.adjust(3, 1)
    return kb.as_markup()

def period_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Ежемесячно", callback_data="add:per:monthly")
    kb.button(text="Раз в год", callback_data="add:per:yearly")
    kb.adjust(2)
    return kb.as_markup()

def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Сохранить", callback_data="add:save")
    kb.button(text="✏️ Исправить", callback_data="add:edit")
    kb.button(text="❌ Отмена", callback_data="add:cancel")
    kb.adjust(1)
    return kb.as_markup()

def list_actions_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚙️ Управлять подписками", callback_data="subs:manage")
    kb.button(text="➕ Добавить", callback_data="menu:add")
    kb.adjust(1)
    return kb.as_markup()

def ok_kb(kind: str, reminder_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ок", callback_data=f"ok:{kind}:{reminder_id}")
    kb.adjust(1)
    return kb.as_markup()

def sub_card_kb(sub_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔕 Отключить напоминания", callback_data=f"sub:disable:{sub_id}")
    kb.button(text="🗑 Удалить из списка", callback_data=f"sub:delete:{sub_id}")
    kb.button(text="📎 Как отменить в сервисе", callback_data=f"sub:how:{sub_id}")
    kb.button(text="↩️ Назад", callback_data="subs:manage")
    kb.adjust(1)
    return kb.as_markup()

def how_cancel_kb(sub_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Apple ID", callback_data=f"cancel:apple:{sub_id}")
    kb.button(text="▶️ Google Play", callback_data=f"cancel:google:{sub_id}")
    kb.button(text="🌐 На сайте", callback_data=f"cancel:web:{sub_id}")
    kb.button(text="❓ Не помню", callback_data=f"cancel:unknown:{sub_id}")
    kb.button(text="↩️ Назад", callback_data=f"sub:open:{sub_id}")
    kb.adjust(2, 2, 1)
    return kb.as_markup()
