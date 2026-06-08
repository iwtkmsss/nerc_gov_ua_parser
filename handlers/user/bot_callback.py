from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from keyboards import subscribed_kb, subscribe_kb
from misc import BDB
from misc.util import format_monitoring_log

router = Router()


@router.callback_query(F.data == "subscribe")
async def subscribe(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    BDB.subscribe_user(user_id)
    user = BDB.get_user(user_id)
    await callback_query.message.edit_text(
        format_monitoring_log(user, BDB.get_monitoring_log()),
        reply_markup=subscribed_kb
    )
    await callback_query.answer("Підписку увімкнено")


@router.callback_query(F.data == "decline_subscribe")
async def decline_subscribe(callback_query: CallbackQuery):
    BDB.add_user(callback_query.from_user.id)
    await callback_query.message.edit_text(
        "Добре. Коли захочете підписатися, натисніть /start.",
        reply_markup=subscribe_kb
    )
    await callback_query.answer()


@router.callback_query(F.data == "show_log")
async def show_log(callback_query: CallbackQuery):
    user = BDB.get_user(callback_query.from_user.id)
    if user is None or not user.get("is_subscribed"):
        await callback_query.message.edit_text(
            "Ви ще не підписані на відстежування.",
            reply_markup=subscribe_kb
        )
        await callback_query.answer()
        return

    try:
        await callback_query.message.edit_text(
            format_monitoring_log(user, BDB.get_monitoring_log()),
            reply_markup=subscribed_kb
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise

    await callback_query.answer("Лог оновлено")


@router.callback_query(F.data == "unsubscribe")
async def unsubscribe(callback_query: CallbackQuery):
    BDB.unsubscribe_user(callback_query.from_user.id)
    await callback_query.message.edit_text(
        "Підписку вимкнено. Повідомлення про зміни більше не надсилатимуться.",
        reply_markup=subscribe_kb
    )
    await callback_query.answer("Підписку вимкнено")
