from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_back_button(callback: str = "home"):
    return InlineKeyboardButton(text="🔙 Назад", callback_data=callback)


def get_back_markup(callback: str = "home"):
    return InlineKeyboardMarkup(inline_keyboard=[[get_back_button(callback)]])
