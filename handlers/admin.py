from aiogram import Router, F, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_subscription, update_balance, get_db_pool, remove_subscription
from config import ADMIN_ID
from datetime import datetime
import asyncio

router = Router()

# FSM for Broadcast
class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm_send = State()

# FSM for User Management
class UserManageState(StatesGroup):
    waiting_for_user_id = State()

def admin_filter(message: types.Message):
    return message.from_user.id == ADMIN_ID

def admin_kb():
    kb = [
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👤 Управление юзером", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📊 Общая статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🗑 Очистить БД (Сообщения)", callback_data="admin_clean_db")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def user_manage_kb(user_id):
    kb = [
        [InlineKeyboardButton(text="📅 +7 Дней", callback_data=f"adm_add_sub_{user_id}_7"),
         InlineKeyboardButton(text="📅 +30 Дней", callback_data=f"adm_add_sub_{user_id}_30")],
        [InlineKeyboardButton(text="❌ Снять подписку", callback_data=f"adm_rem_sub_{user_id}")],
        [InlineKeyboardButton(text="💰 +100 Звезд", callback_data=f"adm_add_bal_{user_id}_100"),
         InlineKeyboardButton(text="💰 +500 Звезд", callback_data=f"adm_add_bal_{user_id}_500")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_home")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(Command("admin"), lambda m: m.from_user.id == ADMIN_ID)
async def cmd_admin(message: types.Message):
    await message.answer("🛠 **Админ-панель**", reply_markup=admin_kb())

@router.callback_query(F.data == "admin_home", lambda c: c.from_user.id == ADMIN_ID)
async def cb_admin_home(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 **Админ-панель**", reply_markup=admin_kb())

# --- Broadcast Logic ---
@router.callback_query(F.data == "admin_broadcast", lambda c: c.from_user.id == ADMIN_ID)
async def cb_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✍️ Введите сообщение для рассылки (можно с фото/видео):")
    await state.set_state(BroadcastState.waiting_for_message)

@router.message(BroadcastState.waiting_for_message, lambda m: m.from_user.id == ADMIN_ID)
async def process_broadcast_msg(message: types.Message, state: FSMContext):
    # Determine message content
    msg_id = message.message_id
    chat_id = message.chat.id
    
    await state.update_data(broadcast_msg_id=msg_id, broadcast_chat_id=chat_id)
    
    # Send preview (copy back to admin)
    await message.copy_to(chat_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_home")]
    ])
    await message.answer("👆 Предпросмотр. Отправить?", reply_markup=kb)
    await state.set_state(BroadcastState.confirm_send)

@router.callback_query(F.data == "broadcast_confirm", BroadcastState.confirm_send, lambda c: c.from_user.id == ADMIN_ID)
async def execute_broadcast(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg_id = data['broadcast_msg_id']
    from_chat = data['broadcast_chat_id']
    
    await callback.message.edit_text("🚀 Рассылка запущена...")
    
    # Get all users (Simple raw query)
    pool = get_db_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")
    
    count = 0
    blocked = 0
    
    for row in users:
        try:
            await bot.copy_message(chat_id=row['user_id'], from_chat_id=from_chat, message_id=msg_id)
            count += 1
            await asyncio.sleep(0.05) # Rate limit safe
        except Exception:
            blocked += 1
            
    await callback.message.answer(f"✅ Рассылка завершена!\n📨 Доставлено: {count}\n🚫 Бот заблокирован: {blocked}")
    await state.clear()
    await callback.message.answer("🛠 **Админ-панель**", reply_markup=admin_kb())

# --- Database Cleanup Logic ---
@router.callback_query(F.data == "admin_clean_db", lambda c: c.from_user.id == ADMIN_ID)
async def cb_clean_db_confirm(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить ВСЕ сообщения", callback_data="admin_clean_db_exec")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_home")]
    ])
    await callback.message.edit_text("⚠️ **Вы уверены?**\nЭто удалит все сохраненные бизнес-сообщения из базы данных (кэш).", reply_markup=kb)

@router.callback_query(F.data == "admin_clean_db_exec", lambda c: c.from_user.id == ADMIN_ID)
async def cb_clean_db_exec(callback: types.CallbackQuery):
    pool = get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE business_messages")
    
    await callback.answer("✅ База сообщений очищена!")
    await callback.message.edit_text("🗑 **База данных сообщений успешно очищена.**", reply_markup=admin_kb())

# --- User Management Logic ---
@router.callback_query(F.data == "admin_find_user", lambda c: c.from_user.id == ADMIN_ID)
async def cb_find_user(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 Введите ID пользователя или @username:")
    await state.set_state(UserManageState.waiting_for_user_id)

@router.message(UserManageState.waiting_for_user_id, lambda m: m.from_user.id == ADMIN_ID)
async def process_find_user(message: types.Message, state: FSMContext):
    query = message.text.strip()
    user = None
    
    pool = get_db_pool()
    async with pool.acquire() as conn:
        if query.isdigit():
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", int(query))
        elif query.startswith("@"):
            username = query[1:]
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        else:
            # Try username without @
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", query)

    if not user:
        await message.answer("❌ Пользователь не найден. Попробуйте снова или нажмите /cancel")
        return

    # Show info
    user_id = user['user_id']
    text = (
        f"👤 <b>Пользователь:</b> <a href='tg://user?id={user_id}'>{user['first_name']}</a>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: {user['balance']} ⭐️\n"
        f"📅 Подписка: {user['subscription_end']}\n"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=user_manage_kb(user_id))
    await state.clear()

@router.callback_query(F.data.startswith("adm_add_sub_"), lambda c: c.from_user.id == ADMIN_ID)
async def cb_adm_add_sub(callback: types.CallbackQuery):
    _, _, _, user_id_str, days_str = callback.data.split("_")
    user_id = int(user_id_str)
    days = int(days_str)
    
    await update_subscription(user_id, days)
    user = await get_user(user_id)
    
    await callback.answer(f"✅ Добавлено {days} дней!")
    
    # Refresh info
    text = (
        f"👤 <b>Пользователь:</b> <a href='tg://user?id={user_id}'>{user['first_name']}</a>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: {user['balance']} ⭐️\n"
        f"📅 Подписка: {user['subscription_end']}\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=user_manage_kb(user_id))

@router.callback_query(F.data.startswith("adm_rem_sub_"), lambda c: c.from_user.id == ADMIN_ID)
async def cb_adm_rem_sub(callback: types.CallbackQuery):
    _, _, _, user_id_str = callback.data.split("_")
    user_id = int(user_id_str)
    
    await remove_subscription(user_id)
    user = await get_user(user_id)
    
    await callback.answer("✅ Подписка снята!")
    
    # Refresh info
    text = (
        f"👤 <b>Пользователь:</b> <a href='tg://user?id={user_id}'>{user['first_name']}</a>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: {user['balance']} ⭐️\n"
        f"📅 Подписка: {user['subscription_end']}\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=user_manage_kb(user_id))

@router.callback_query(F.data.startswith("adm_add_bal_"), lambda c: c.from_user.id == ADMIN_ID)
async def cb_adm_add_bal(callback: types.CallbackQuery):
    _, _, _, user_id_str, amount_str = callback.data.split("_")
    user_id = int(user_id_str)
    amount = float(amount_str)
    
    await update_balance(user_id, amount)
    user = await get_user(user_id)
    
    await callback.answer(f"✅ Добавлено {amount} Stars!")
    
    # Refresh info
    text = (
        f"👤 <b>Пользователь:</b> <a href='tg://user?id={user_id}'>{user['first_name']}</a>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: {user['balance']} ⭐️\n"
        f"📅 Подписка: {user['subscription_end']}\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=user_manage_kb(user_id))
