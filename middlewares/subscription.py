from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery, BusinessConnection
from database import get_user, add_user
from datetime import datetime
import logging

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_obj = None
        
        # We assume this middleware is registered on dp.update.middleware, 
        # so 'event' is an Update object.
        if isinstance(event, Update):
            if event.message:
                user_obj = event.message.from_user
            elif event.business_message:
                user_obj = event.business_message.from_user
            elif event.edited_business_message:
                user_obj = event.edited_business_message.from_user
            elif event.business_connection:
                user_obj = event.business_connection.user
            elif event.callback_query:
                user_obj = event.callback_query.from_user
            elif event.pre_checkout_query:
                user_obj = event.pre_checkout_query.from_user
            elif event.message_reaction:
                user_obj = event.message_reaction.user
                
        # If registered on router.message.middleware, event is Message, etc.
        # Fallback for that case if someone changes registration
        elif hasattr(event, "from_user"):
            user_obj = event.from_user
        elif isinstance(event, BusinessConnection):
            user_obj = event.user

        user = None
        if user_obj:
            # Ensure user exists
            user = await get_user(user_obj.id)
            if not user:
                await add_user(user_obj.id, user_obj.username, user_obj.first_name)
                user = await get_user(user_obj.id)
        
        subscription_active = False
        if user:
            sub_end = user['subscription_end']
            if isinstance(sub_end, str):
                try:
                    sub_end = datetime.fromisoformat(sub_end)
                except ValueError:
                    sub_end = datetime.min
            if sub_end and sub_end > datetime.now():
                subscription_active = True
        
        data['subscription_active'] = subscription_active
        data['db_user'] = user
        
        return await handler(event, data)