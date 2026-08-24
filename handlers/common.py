from aiogram import Router, F, types
from aiogram.filters import Command
from database import get_user, get_stats, get_user_connections
from redis_client import get_redis
from config import WATERMARK
from keyboards import main_menu, subscription_menu, settings_menu, back_kb, profile_kb
import json

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, db_user):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот для управления бизнес-аккаунтом.\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery, db_user):
    connections = await get_user_connections(callback.from_user.id)
    sub_end = db_user['subscription_end']
    balance = db_user['balance']
    
    text = (
        f"👤 **Профиль**\n"
        f"🆔 ID: `{callback.from_user.id}`\n"
        f"💰 Баланс: {balance} ⭐️\n"
        f"📅 Подписка до: {sub_end}\n"
        f"🔗 Подключений: {len(connections)}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=profile_kb())

@router.callback_query(F.data == "subscription")
async def cb_subscription(callback: types.CallbackQuery, db_user):
    text = (
        "💳 <b>Премиум Доступ</b>\n\n"
        "<blockquote expandable>"
        "🚀 <b>Что дает подписка:</b>\n\n"
        "✅ <b>Безлимитные подключения</b>\n"
        "✅ <b>Сохранение медиа (.save)</b>\n"
        "✅ <b>История изменений</b>\n"
        "✅ <b>Приоритетная поддержка</b>"
        "</blockquote>\n\n"
        "👇 <i>Выберите тариф:</i>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=subscription_menu(has_trial=not db_user['trial_used'])
    )

@router.callback_query(F.data == "settings")
async def cb_settings(callback: types.CallbackQuery):
    redis = await get_redis()
    # Check if notif enabled (default true)
    key = f"settings:notif:{callback.from_user.id}"
    val = await redis.get(key)
    notif_enabled = val != "0"
    
    await callback.message.edit_text(
        "⚙️ **Настройки**",
        reply_markup=settings_menu(notif_enabled)
    )

@router.callback_query(F.data == "toggle_notif")
async def cb_toggle_notif(callback: types.CallbackQuery):
    redis = await get_redis()
    key = f"settings:notif:{callback.from_user.id}"
    val = await redis.get(key)
    new_val = "0" if val != "0" else "1"
    await redis.set(key, new_val)
    
    await callback.message.edit_text(
        "⚙️ **Настройки**",
        reply_markup=settings_menu(new_val == "1")
    )

@router.callback_query(F.data == "stats")
async def cb_stats(callback: types.CallbackQuery):
    conns, msgs = await get_stats()
    await callback.message.edit_text(
        f"📊 **Статистика**\n"
        f"📡 Всего подключений: {conns}\n"
        f"📨 Обработано сообщений: {msgs}",
        reply_markup=back_kb()
    )

@router.callback_query(F.data == "back_start")
async def cb_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=main_menu()
    )
