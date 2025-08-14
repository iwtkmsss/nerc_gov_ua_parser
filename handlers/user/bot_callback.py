from aiogram import Router, F
from aiogram.types import CallbackQuery


router = Router()


@router.callback_query(F.data == "test")
async def get_material_call(callback_query: CallbackQuery):
    await callback_query.message.answer("test")
