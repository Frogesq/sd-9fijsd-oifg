from aiogram import Router, F, types, Bot
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted
from database import add_connection, add_message, get_connection
from redis_client import get_redis
from config import CURRENCY, WATERMARK
import json
import logging
import os
from html import escape
from aiogram.types import FSInputFile

router = Router()
# ... (rest of imports and helper functions)

async def get_connection_owner(connection_id: str):
    conn = await get_connection(connection_id)
    if conn:
        return conn['user_id']
    return None

async def notify_user(bot: Bot, user_id: int, text: str):
    try:
        redis = await get_redis()
        notif_setting = await redis.get(f"settings:notif:{user_id}")
        if notif_setting == "0":
            return
        await bot.send_message(user_id, text + WATERMARK, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Failed to notify user {user_id}: {e}")

@router.business_connection()

async def on_business_connection(event: BusinessConnection, bot: Bot):

    user_id = event.user.id

    permissions = {

        "can_reply": event.can_reply,

        "is_enabled": event.is_enabled

    }

    

    # If connection is disabled/removed

    if not event.is_enabled:

        # Update DB to reflect disabled state (optional, but good for sync)

        # We still add/update connection but with is_enabled=False

        pass



    await add_connection(

        user_id, event.id, event.user_chat_id, 

        "Business Chat",

        event.user.username, permissions

    )

    

    redis = await get_redis()

    

    if event.is_enabled:

        await redis.set(f"connection_owner:{event.id}", user_id)

        await notify_user(bot, user_id, f"✅ Подключён бизнес-чат ID:{event.id}")

    else:

        # Connection disabled

        await redis.delete(f"connection_owner:{event.id}")

        await notify_user(bot, user_id, f"❌ Бизнес-чат отключён ID:{event.id}")



@router.business_message()
async def on_business_message(message: Message, bot: Bot, subscription_active: bool):
    if not message.business_connection_id:
        return

    redis = await get_redis()
    user_id = await get_connection_owner(message.business_connection_id)
    
    # 1. Handle Commands from Owner (.status, .save)
    if user_id and message.from_user.id == user_id:
        if message.text == ".status":
            try:
                await message.edit_text("pong")
            except Exception:
                pass
            return # Don't cache/notify this command

        if message.text in [".save", ".s", ".safe"] and message.reply_to_message:
            # Check Premium
            if not subscription_active:
                await notify_user(bot, user_id, "🔒 <b>Функция доступна только в Premium</b>\n<i>Оформите подписку в меню бота.</i>")
                try:
                    await message.delete()
                except:
                    pass
                return

            # Delete command immediately for stealth/safety
            try:
                await message.delete()
            except Exception:
                pass

            try:
                target = message.reply_to_message
                chat_name = message.chat.title or "Private"
                caption = f"🧨 Сохраненное сообщение из {escape(chat_name)}" + WATERMARK
                
                # Identify media and file_id
                file_id = None
                media_type_local = None
                
                if target.photo:
                    file_id = target.photo[-1].file_id
                    media_type_local = "photo"
                elif target.video:
                    file_id = target.video.file_id
                    media_type_local = "video"
                elif target.voice:
                    file_id = target.voice.file_id
                    media_type_local = "voice"
                elif target.video_note:
                    file_id = target.video_note.file_id
                    media_type_local = "video_note"
                elif target.audio:
                    file_id = target.audio.file_id
                    media_type_local = "audio"

                if file_id:
                    # Download, send, and delete
                    file = await bot.get_file(file_id)
                    temp_path = f"save_{file_id}_{os.path.basename(file.file_path)}"
                    await bot.download_file(file.file_path, temp_path)
                    
                    try:
                        input_file = FSInputFile(temp_path)
                        if media_type_local == "photo":
                            await bot.send_photo(user_id, input_file, caption=caption, parse_mode="HTML")
                        elif media_type_local == "video":
                            await bot.send_video(user_id, input_file, caption=caption, parse_mode="HTML")
                        elif media_type_local == "voice":
                            await bot.send_voice(user_id, input_file, caption=caption, parse_mode="HTML")
                        elif media_type_local == "audio":
                            await bot.send_audio(user_id, input_file, caption=caption, parse_mode="HTML")
                        elif media_type_local == "video_note":
                            await bot.send_video_note(user_id, input_file)
                            await bot.send_message(user_id, caption, parse_mode="HTML")
                        
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                else:
                    # Fallback to copy for other types (text, sticker, etc)
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=target.message_id,
                        caption=caption,
                        parse_mode="HTML"
                    )

            except Exception as e:
                await notify_user(bot, user_id, f"⚠️ Не удалось сохранить медиа: {e}")
            return

        if message.text in [".messageinfo", ".info"] and message.reply_to_message:
            if not subscription_active:
                await notify_user(bot, user_id, "🔒 <b>Функция доступна только в Premium</b>")
                return

            try:
                # Get raw dict
                msg_dict = message.reply_to_message.model_dump(mode='json', exclude_none=True)
                json_str = json.dumps(msg_dict, indent=2, ensure_ascii=False)
                
                if len(json_str) > 4000:
                    # Send as file if too long
                    temp_file = f"message_{message.reply_to_message.message_id}.json"
                    with open(temp_file, "w", encoding="utf-8") as f:
                        f.write(json_str)
                    
                    input_file = FSInputFile(temp_file)
                    await bot.send_document(
                        user_id, 
                        input_file, 
                        caption=f"ℹ️ Raw Data for message {message.reply_to_message.message_id}" + WATERMARK
                    )
                    os.remove(temp_file)
                else:
                    # Send as text
                    await bot.send_message(
                        user_id,
                        f"ℹ️ <b>Raw Message Data:</b>\n<blockquote expandable>{escape(json_str)}</blockquote>" + WATERMARK,
                        parse_mode="HTML"
                    )
                
                await message.delete()
            except Exception as e:
                await notify_user(bot, user_id, f"⚠️ Ошибка получения инфо: {e}")
            return # Don't cache this command

        if message.text and message.text.startswith(".spam "):
            # Format: .spam <count> <text>
            try:
                args = message.text.split(" ", 2)
                if len(args) < 3:
                    return

                count = int(args[1])
                spam_text = args[2]
                
                # Limit count for safety
                if count > 100:
                    count = 100
                
                # Delete command message
                try:
                    await message.delete()
                except:
                    pass
                
                # Send spam
                import asyncio
                for _ in range(count):
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=spam_text,
                        business_connection_id=message.business_connection_id
                    )
                    await asyncio.sleep(0.05) # Rate limit
                    
            except Exception as e:
                 logging.error(f"Spam error: {e}")
            return

        if message.text == ".heart":
            try:
                # Sequence of frames building a heart
                frames = [
                    "▫️",
                    "▫️▫️▫️\n▫️▫️▫️\n  ▫️",
                    "  ▫️▫️    ▫️▫️  \n▫️▫️▫️▫️▫️▫️▫️\n▫️▫️▫️▫️▫️▫️▫️\n  ▫️▫️▫️▫️▫️  \n    ▫️▫️▫️    \n      ▫️      ",
                    "  ❤️❤️    ❤️❤️  \n❤️❤️❤️❤️❤️❤️❤️\n❤️❤️❤️❤️❤️❤️❤️\n  ❤️❤️❤️❤️❤️  \n    ❤️❤️❤️    \n      ❤️      ",
                    "  💖💖    💖💖  \n💖💖💖💖💖💖💖\n💖💖💖💖💖💖💖\n  💖💖💖💖💖  \n    💖💖💖    \n      💖      ",
                    "  💗💗    💗💗  \n💗💗💗💗💗💗💗\n💗💗💗💗💗💗💗\n  💗💗💗💗💗  \n    💗💗💗    \n      💗      ",
                    "❤️ <b><i>LunoView Business</i></b>"
                ]
                
                import asyncio
                for frame in frames:
                    try:
                        await message.edit_text(frame, parse_mode="HTML")
                        await asyncio.sleep(0.8)
                    except:
                        break 
                    
            except Exception as e:
                logging.error(f"Heart error: {e}")
            return

    # Determine Media Type for Cache
    media_type = "text"
    file_id = None
    
    if message.photo: 
        media_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video: 
        media_type = "video"
        file_id = message.video.file_id
    elif message.voice: 
        media_type = "voice"
        file_id = message.voice.file_id
    elif message.audio: 
        media_type = "audio"
        file_id = message.audio.file_id
    elif message.document: 
        media_type = "document"
        file_id = message.document.file_id
    elif message.sticker: 
        media_type = "sticker"
        file_id = message.sticker.file_id
    elif message.video_note: 
        media_type = "video_note"
        file_id = message.video_note.file_id
    elif message.animation: 
        media_type = "animation"
        file_id = message.animation.file_id

    # Cache message
    msg_data = {
        "connection_id": message.business_connection_id,
        "message_id": message.message_id,
        "chat_id": message.chat.id,
        "chat_title": message.chat.title or "Private",
        "chat_username": message.chat.username,
        "from_user_id": message.from_user.id,
        "from_username": message.from_user.username,
        "text": message.text or message.caption or "",
        "media_type": media_type,
        "media_file_id": file_id,
        "date": message.date.isoformat(),
        "is_cached": True
    }
    
    # Save to DB
    await add_message(msg_data)
    
    # Redis cache (TTL 1 week)
    key = f"msg_cache:{message.business_connection_id}:{message.message_id}"
    await redis.set(key, json.dumps(msg_data), ex=604800)

@router.edited_business_message()
async def on_edited_business_message(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
        
    redis = await get_redis()
    key = f"msg_cache:{message.business_connection_id}:{message.message_id}"
    old_data_json = await redis.get(key)
    old_text = ""
    from_user_name = "Пользователь"
    
    if old_data_json:
        old_data = json.loads(old_data_json)
        old_text = old_data.get("text", "")
        from_user_id = old_data.get("from_user_id")
        # Try to get username from cache if possible, or use current
        from_user_name = message.from_user.full_name
        
        old_data["text"] = message.text or message.caption or ""
        await redis.set(key, json.dumps(old_data), ex=604800)
    
    user_id = await get_connection_owner(message.business_connection_id)
    if user_id and message.from_user.id != user_id:
        # Check Premium
        from database import get_user
        db_user = await get_user(user_id)
        is_premium = False
        if db_user and db_user['subscription_end']:
            import datetime
            if db_user['subscription_end'] > datetime.datetime.now():
                is_premium = True

        safe_chat_title = escape(message.chat.title or message.chat.first_name or "Чат")
        safe_user_name = escape(message.from_user.full_name)
        
        if not is_premium:
            text = (
                f"✏️ <b>{safe_chat_title}</b> | {safe_user_name}\n"
                f"📝 Сообщение отредактировано\n"
                f"🔒 <i>История изменений доступна в Premium</i>"
            )
            await notify_user(bot, user_id, text)
            return

        safe_old = escape(old_text)
        safe_new = escape(message.text or message.caption or "")
        
        if message.chat.username:
            msg_link = f"https://t.me/{message.chat.username}/{message.message_id}"
        else:
            msg_link = f"tg://openmessage?user_id={message.chat.id}&message_id={message.message_id}"
            
        text = (
            f"✏️ <b>{safe_chat_title}</b> | {safe_user_name}\n"
            f"📝 <a href='{msg_link}'>Сообщение</a> отредактировано\n"
            f"<b>Было:</b>\n<blockquote expandable>{safe_old}</blockquote>\n"
            f"<b>Стало:</b>\n<blockquote expandable>{safe_new}</blockquote>"
        )
        await notify_user(bot, user_id, text)

@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    if not event.business_connection_id:
        return
    
    redis = await get_redis()
    user_id = await get_connection_owner(event.business_connection_id)
    
    if user_id:
        # Check Subscription for User
        # We need to fetch user from DB to check sub
        # Optimization: cache sub status in redis too? 
        # For now let's query DB.
        from database import get_user
        db_user = await get_user(user_id)
        is_premium = False
        if db_user and db_user['subscription_end']:
            import datetime
            if db_user['subscription_end'] > datetime.datetime.now():
                is_premium = True
        
        if not is_premium:
            # Fallback for non-premium
            chat_info = "Неизвестного пользователя"
            if event.chat:
                safe_title = escape(event.chat.title or event.chat.first_name or 'Пользователя')
                chat_info = f'<b>{safe_title}</b>'
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔐 Посмотреть", callback_data="subscription")]
            ])
            await notify_user(bot, user_id, f"🗑️ Удалено сообщение у {chat_info}\n🔒 <i>Содержимое скрыто (Premium)</i>")
            return

        # Try to get chat info from event.chat if available
        chat_info = "Неизвестного пользователя"
        if event.chat:
            safe_title = escape(event.chat.title or event.chat.first_name or 'Пользователя')
            if event.chat.username:
                chat_info = f'<a href="tg://resolve?domain={event.chat.username}">{safe_title}</a>'
            else:
                chat_info = f'<b>{safe_title}</b>'
        
        deleted_texts = []
        for msg_id in event.message_ids:
            key = f"msg_cache:{event.business_connection_id}:{msg_id}"
            data_json = await redis.get(key)
            if data_json:
                data = json.loads(data_json)
                # Skip notifications if the deleted message was from the owner
                if data.get("from_user_id") == user_id:
                    continue
                    
                text_content = data.get("text", "")
                media_type = data.get("media_type", "text")
                file_id = data.get("media_file_id")
                
                if file_id and media_type != "text":
                    # Send media immediately
                    caption = f"🗑️ Удалено {media_type} у {chat_info}"
                    if text_content:
                        caption += f"\n<blockquote expandable>{escape(text_content)}</blockquote>"
                    
                    caption += WATERMARK

                    try:
                        if media_type == "photo":
                            await bot.send_photo(user_id, file_id, caption=caption, parse_mode="HTML")
                        elif media_type == "video":
                            await bot.send_video(user_id, file_id, caption=caption, parse_mode="HTML")
                        elif media_type == "voice":
                            await bot.send_voice(user_id, file_id, caption=caption, parse_mode="HTML")
                        elif media_type == "audio":
                            await bot.send_audio(user_id, file_id, caption=caption, parse_mode="HTML")
                        elif media_type == "document":
                            await bot.send_document(user_id, file_id, caption=caption, parse_mode="HTML")
                        elif media_type == "sticker":
                            await bot.send_sticker(user_id, file_id)
                            await notify_user(bot, user_id, f"🗑️ Удален стикер выше у {chat_info}")
                        elif media_type == "video_note":
                            await bot.send_video_note(user_id, file_id)
                            await notify_user(bot, user_id, f"🗑️ Удален кружочек выше у {chat_info}")
                        elif media_type == "animation":
                            await bot.send_animation(user_id, file_id, caption=caption, parse_mode="HTML")
                        else:
                            deleted_texts.append(escape(f"[{media_type}] {text_content}"))
                    except Exception as e:
                        logging.error(f"Failed to send deleted media {msg_id}: {e}")
                        deleted_texts.append(escape(f"[Error sending {media_type}] {text_content}"))
                        
                else:
                    if not text_content:
                        text_content = "[Empty]"
                    deleted_texts.append(escape(text_content))
            else:
                deleted_texts.append(f"Msg {msg_id}")
        
        if deleted_texts:
            text_summary = "\n".join(deleted_texts)
            await notify_user(bot, user_id, f"🗑️ Удалено сообщение у {chat_info}:\n<blockquote expandable>{text_summary}</blockquote>")

@router.message(F.reply_to_message.business_connection_id)
async def on_reply_to_business(message: Message, bot: Bot):
    bc_id = message.reply_to_message.business_connection_id
    try:
        await bot.send_message(
            chat_id=message.reply_to_message.chat.id,
            text=(message.text or "") + WATERMARK,
            business_connection_id=bc_id
        )
    except Exception as e:
        logging.error(f"Failed to reply to business message: {e}")

# Removed on_business_reaction as requested
