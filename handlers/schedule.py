from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
import html

from keyboards.schedule_keyboards import get_schedule_keyboard
from parser import get_old_data, parse_districts


schedule_router = Router()


@schedule_router.message(Command("schedule"))
async def schedule(message: Message):
    await message.answer("Выберите смену", reply_markup=get_schedule_keyboard())


@schedule_router.callback_query(F.data.startswith("districts:"))
async def show_districts(callback: CallbackQuery):
    if callback.data and callback.message:
        shift_index = int(callback.data.split(":")[1])
        text = f"<b>{get_old_data()[shift_index]["name"]}\nОбразовательные направления:</b>\n\n"
        programs = await parse_districts(shift_index)
        for district, program in programs.items():
            text += f"{district} — {program}\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


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
        markup = None
        if "Положение об образовательной смене" in shift["docs"]:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Направления", callback_data=f"districts:{shift_index}")]
            ])
        await callback.message.answer(
            text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
        )
    await callback.answer()
