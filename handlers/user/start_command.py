from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from misc import BDB
from keyboards import subscribed_kb, subscribe_kb
from misc.util import format_monitoring_log

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user = BDB.get_user(user_id)

    if user is None:
        BDB.add_user(user_id)
        await message.answer(
            "Вітаю. Підписатися на відстежування змін на сайті НКРЕКП?",
            reply_markup=subscribe_kb
        )
    elif user.get("is_subscribed"):
        await message.answer(
            format_monitoring_log(user, BDB.get_monitoring_log()),
            reply_markup=subscribed_kb
        )
    else:
        await message.answer(
            "Ви вже зареєстровані, але ще не підписані на відстежування.",
            reply_markup=subscribe_kb
        )
