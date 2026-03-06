from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
import html

from keyboards.schedule_keyboards import get_schedule_keyboard
from parser import get_old_data


schedule_router = Router()


@schedule_router.message(Command("schedule"))
async def schedule(message: Message):
    await message.answer("Выберите смену", reply_markup=get_schedule_keyboard())


@schedule_router.callback_query(F.data.startswith("shift-info:"))
async def show_shift_info(callback: CallbackQuery):
    if callback.data and callback.message:
        shift_index = int(callback.data.split(":")[1])
        shifts = get_old_data()
        shift = shifts[shift_index]
        text = (
            f"<b>{shift["name"]}</b>\n"
            f"<i>{shift["date"]}</i>\n\n"
            f"Подача {shift["feed"]}"
        )
        if shift["docs"]:
            text += "\n\n<b>Документы:</b>\n"
            for name, file_link in shift["docs"].items():
                text += (
                    f'<a href="{html.escape(file_link)}">{html.escape(name)}</a>\n'
                )
        await callback.message.answer(
            text, parse_mode="HTML", disable_web_page_preview=True
        )
    await callback.answer()
