from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
import html

from keyboards.schedule_keyboards import get_schedule_keyboard, get_regions_keyboard
from parser import get_old_data, get_districts, get_spiski
from database import get_user_id_by_name, check_username


schedule_router = Router()


@schedule_router.message(Command("schedule"))
async def schedule(message: Message):
    if not message.from_user:
        return
    check_username(message.from_user.id, message.from_user.username)
    await message.answer("📄 Выберите смену", reply_markup=get_schedule_keyboard())


@schedule_router.callback_query(F.data.startswith("districts:"))
async def show_districts(callback: CallbackQuery):
    if callback.data and callback.message:
        check_username(callback.from_user.id, callback.from_user.username)
        shift_index = int(callback.data.split(":")[1])
        name = get_old_data()[shift_index]["name"]
        text = f"📌 <b>{name}\nОбразовательные направления:</b>\n\n"
        programs = get_districts(name)
        if programs:
            for district, program in programs.items():
                if district == "Информационные и компьютерные технологии":
                    district = f"⚠️⚠️⚠️ {district} ⚠️⚠️⚠️"
                if program in ("Искусственный интеллект", "Прототипирование", "Цифровой ритейл"):
                    program = f"⛔️ {program} ⛔️"
                text += f"{district} — {program}\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@schedule_router.callback_query(F.data.startswith("spiski:"))
async def show_spiski(callback: CallbackQuery):
    if callback.data and callback.message:
        data = callback.data.split(":")
        shift_index = int(data[1])
        name = get_old_data()[shift_index]["name"]
        spiski = get_spiski(name)
        keys = sorted(spiski.keys()) # pyright: ignore[reportOptionalMemberAccess]
        if len(data) == 2:
            text = f"📌 <b>{name}\nОбразовательные направления:</b>\n\n"
            markup = get_regions_keyboard(shift_index, keys)
            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
        elif len(data) == 3:
            district_index = int(data[2])
            text = f'😸 <b>Прошедшие на образовательное направление "{keys[district_index]}</b>":\n\n'
            for person in spiski[keys[district_index]]: # pyright: ignore[reportOptionalSubscript]
                line = " ".join((person["surname"], person["name"], person["patronymic"]))
                if user_id := get_user_id_by_name(person["name"], person["surname"]):
                    line = f'<a href="tg://user?id={html.escape(str(user_id))}">{html.escape(line)}</a>'
                line += "\n"
                text += line
            await callback.message.answer(text, parse_mode='HTML')
    await callback.answer()


@schedule_router.callback_query(F.data.startswith("shift-info:"))
async def show_shift_info(callback: CallbackQuery):
    if callback.data and callback.message:
        shift_index = int(callback.data.split(":")[1])
        shifts = get_old_data()
        shift = shifts[shift_index]
        text = (
            f"📌 <b>{shift["name"]}</b>\n"
            f"📆 <i>{shift["date"]}</i>\n\n"
            f"🗳 Подача {shift["feed"]}"
        )
        if shift["docs"]:
            text += "\n\n📑 <b>Документы:</b>\n"
            for name, file_link in shift["docs"].items():
                text += (
                    f'<a href="{html.escape(file_link)}">{html.escape(name)}</a>\n'
                )
        markup = []
        if "Положение об образовательной смене" in shift["docs"]:
            markup.append([InlineKeyboardButton(text="🗂 Направления", callback_data=f"districts:{shift_index}")])
        for doc in shift["docs"]:
            if "Списочный состав групп учащихся, зачисленных" in doc:
                markup.append([InlineKeyboardButton(text="👀 Кто прошел?", callback_data=f"spiski:{shift_index}")])
        markup = InlineKeyboardMarkup(inline_keyboard=markup) if markup else None
        await callback.message.answer(
            text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
        )
    await callback.answer()
