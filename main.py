import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_PORT, ADMIN_ID
from database import init_db, close_db
from handlers import get_handlers
from middlewares.subscription import SubscriptionMiddleware

# Logging
logging.basicConfig(level=logging.INFO)

async def check_expired_subs(app):
    while True:
        try:
            # Here we would query DB for expired subs and maybe notify them
            # logging.info("Checking expired subscriptions...")
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error in background task: {e}")
            await asyncio.sleep(60)

async def on_startup(bot: Bot):
    await init_db()
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}", allowed_updates=[
            "message", "edited_message", "business_connection", 
            "business_message", "edited_business_message", 
            "deleted_business_messages", "message_reaction", 
            "callback_query", "pre_checkout_query", "shipping_query"
        ])
        logging.info(f"Webhook set to {WEBHOOK_URL}{WEBHOOK_PATH}")

async def on_shutdown(app):
    await close_db()

async def start_background_tasks(app):
    app['expired_subs_checker'] = asyncio.create_task(check_expired_subs(app))

async def cleanup_background_tasks(app):
    app['expired_subs_checker'].cancel()
    await app['expired_subs_checker']

def main():
    dp = Dispatcher()
    
    # Middlewares
    dp.update.middleware(SubscriptionMiddleware())
    
    # Handlers
    for router in get_handlers():
        dp.include_router(router)
        
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    
    if WEBHOOK_URL:
        dp.startup.register(on_startup)
        
        app = web.Application()
        
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        
        setup_application(app, dp, bot=bot)
        
        app.on_startup.append(start_background_tasks)
        app.on_cleanup.append(cleanup_background_tasks)
        app.on_cleanup.append(on_shutdown)
        
        web.run_app(app, host="0.0.0.0", port=WEBHOOK_PORT)
    else:
        # Polling mode
        logging.warning("No WEBHOOK_URL found. Starting polling mode.")
        async def run_polling():
            await init_db()
            try:
                await bot.delete_webhook()
                await dp.start_polling(bot, allowed_updates=[
                    "message", "edited_message", "business_connection", 
                    "business_message", "edited_business_message", 
                    "deleted_business_messages", "message_reaction", 
                    "callback_query", "pre_checkout_query"
                ])
            finally:
                await close_db()
            
        asyncio.run(run_polling())

if __name__ == "__main__":
    main()
