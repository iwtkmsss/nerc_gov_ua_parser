from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

subscribe_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Підписатися", callback_data="subscribe"),
        InlineKeyboardButton(text="Не зараз", callback_data="decline_subscribe")
    ]
])

subscribed_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Оновити лог", callback_data="show_log"),
        InlineKeyboardButton(text="Відписатися", callback_data="unsubscribe")
    ]
])

agree_kb = subscribe_kb
