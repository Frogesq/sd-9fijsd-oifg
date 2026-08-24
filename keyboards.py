from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="Профиль", callback_data="profile")
    kb.button(text="Подписка", callback_data="subscription")
    kb.button(text="Настройки", callback_data="settings")
    kb.button(text="Статистика", callback_data="stats")
    kb.adjust(1, 2, 1)
    return kb.as_markup()

def subscription_menu(has_trial=True):
    kb = InlineKeyboardBuilder()
    kb.button(text="Неделя 50 ⭐️", callback_data="buy_week")
    kb.button(text="Месяц 150 ⭐️", callback_data="buy_month")
    kb.button(text="Год 1000 ⭐️", callback_data="buy_year")
    if has_trial:
        kb.button(text="🎁 Пробный 7 дней", callback_data="trial")
    
    kb.button(text="🔙 Назад", callback_data="back_start")
    kb.adjust(1)
    return kb.as_markup()

def profile_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Пополнить баланс", callback_data="top_up")
    kb.button(text="🔙 Назад", callback_data="back_start")
    kb.adjust(1)
    return kb.as_markup()

def settings_menu(notif_enabled=True):
    kb = InlineKeyboardBuilder()
    status = "✅ Вкл" if notif_enabled else "❌ Выкл"
    kb.button(text=f"Уведомления: {status}", callback_data="toggle_notif")
    kb.button(text="🔙 Назад", callback_data="back_start")
    kb.adjust(1)
    return kb.as_markup()

def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back_start")
    return kb.as_markup()

def pay_kb(url: str = None):
    # For XTR, the pay button is handled by the client native UI usually,
    # but for sendInvoice we can add a Pay button if needed or just use the native one.
    # The prompt says "InlineKeyboard(pay=True)". 
    # In aiogram 3, send_invoice adds the pay button automatically.
    # But if we want a manual link or something:
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Оплатить", pay=True)
    if url: # if external
        kb.button(text="🔗 Ссылка", url=url)
    return kb.as_markup()

def top_up_options():
    kb = InlineKeyboardBuilder()
    kb.button(text="100 ⭐️", callback_data="topup_100")
    kb.button(text="500 ⭐️", callback_data="topup_500")
    kb.button(text="1000 ⭐️", callback_data="topup_1000")
    kb.button(text="🔙 Назад", callback_data="profile")
    kb.adjust(3, 1)
    return kb.as_markup()
