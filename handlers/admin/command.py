from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from filter import UserAdmin

router = Router()

@router.message(Command("admin"), UserAdmin())
async def cmd_admin(message: Message):
    text = ""
    await message.answer(text, parse_mode="HTML")


