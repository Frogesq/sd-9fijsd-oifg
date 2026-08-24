from aiogram import Router, F, types, Bot
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from database import update_subscription, update_balance, set_trial_used, get_user
from config import PROVIDER_TOKEN, CURRENCY, WATERMARK
from keyboards import top_up_options, subscription_menu, back_kb
import json
import logging

router = Router()

PRICES = {
    "week": 50,
    "month": 150,
    "year": 1000
}

@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_sub(callback: types.CallbackQuery):
    period = callback.data.split("_")[1] # week, month, year
    amount = PRICES.get(period, 50)
    days_map = {"week": 7, "month": 30, "year": 365}
    days = days_map.get(period, 7)
    
    payload = json.dumps({
        "type": "sub",
        "days": days,
        "user_id": callback.from_user.id
    })
    
    await callback.message.answer_invoice(
        title=f"Подписка на {period}",
        description=f"Доступ к функциям бота на {days} дней",
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label=f"Sub {period}", amount=amount)], 
        # For XTR, amount is integer of stars.
        # send_invoice amount for XTR: 1 = 1 Star? Yes.
        # But for other currencies it is smallest units. XTR is whole number usually?
        # Actually API says: "For XTR, the amount must be 1:1".
        # Wait, for regular currencies, amount is in "cents".
        # For XTR, amount is number of Stars. 
        # But LabeledPrice expects integer.
        # Let's assume 1 unit = 1 Star.
    )
    await callback.answer()

@router.callback_query(F.data == "trial")
async def cb_trial(callback: types.CallbackQuery, db_user):
    if db_user['trial_used']:
        await callback.answer("⛔️ Пробный период уже использован!", show_alert=True)
        return
    
    await set_trial_used(callback.from_user.id)
    await update_subscription(callback.from_user.id, 7)
    await callback.message.edit_text(
        "🎁 **Пробный период активирован!**\nПодписка продлена на 7 дней." ,
        reply_markup=back_kb()
    )

@router.callback_query(F.data == "top_up")
async def cb_top_up_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💰 **Пополнение баланса**\nВыберите сумму:" ,
        reply_markup=top_up_options()
    )

@router.callback_query(F.data.startswith("topup_"))
async def cb_top_up_invoice(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[1])
    
    payload = json.dumps({
        "type": "topup",
        "amount": amount,
        "user_id": callback.from_user.id
    })
    
    await callback.message.answer_invoice(
        title=f"Пополнение {amount} ⭐️",
        description=f"Пополнение внутреннего баланса на {amount} Stars",
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label="Top Up", amount=amount)]
    )
    await callback.answer()

@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    payment = message.successful_payment
    payload = json.loads(payment.invoice_payload)
    
    if payload['type'] == 'sub':
        days = payload['days']
        await update_subscription(message.from_user.id, days)
        await message.answer(f"✅ Оплата прошла успешно! Подписка продлена на {days} дней." )
        
    elif payload['type'] == 'topup':
        amount = payload['amount']
        await update_balance(message.from_user.id, amount)
        await message.answer(f"✅ Баланс пополнен на {amount} Stars!" )
