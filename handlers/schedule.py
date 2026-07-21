from typing import Union

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
import html

from keyboards.schedule_keyboards import get_schedule_keyboard, get_regions_keyboard
from keyboards import get_back_button, get_back_markup
from parser import get_old_data, get_districts, get_spiski, get_dopusheni, get_districts_info
from database import get_user_by_name, check_username, add_user

from tools import get_from_user_and_answer_from_update


schedule_router = Router()


@schedule_router.message(Command("schedule"))
@schedule_router.callback_query(lambda c: c.data == "schedule")
async def schedule(update: Union[Message, CallbackQuery]):
    from_user, answer = get_from_user_and_answer_from_update(update)
    if not from_user or not answer:
        return
    add_user(from_user.id, from_user.username)
    check_username(from_user.id, from_user.username)
    await answer("📄 Выберите смену", reply_markup=get_schedule_keyboard())


@schedule_router.callback_query(F.data.startswith("districts:"))
async def show_districts(callback: CallbackQuery):
    if callback.data and callback.message:
        check_username(callback.from_user.id, callback.from_user.username)
        shift_index = int(callback.data.split(":")[1])
        name = get_old_data()[shift_index]["name"]
        text = f"📌 <b>{name}\nОбразовательные направления:</b>\n\n"
        programs = get_districts(name)
        districts_info = get_districts_info()
        districts_names = sorted(districts_info.keys()) # pyright: ignore[reportOptionalMemberAccess]
        buttons = []
        if programs:
            for district, program in programs.items():
                if district in districts_names:
                    programs_names = sorted(districts_info[district]["programs"].keys()) # pyright: ignore[reportOptionalSubscript]
                    if program in programs_names:
                        buttons.append(InlineKeyboardButton(text=program, callback_data=f"direction_info:{districts_names.index(district)}:{programs_names.index(program)}:districts:{shift_index}"))
                if district == "Информационные и компьютерные технологии":
                    district = f"⚠️⚠️⚠️ {district} ⚠️⚠️⚠️"
                if program in ("Искусственный интеллект", "Прототипирование", "Цифровой ритейл"):
                    program = f"⛔️ {program} ⛔️"
                text += f"{district} — {program}\n"
        buttons.append(get_back_button(f"shift-info:{shift_index}"))
        markup = InlineKeyboardMarkup(inline_keyboard=[[el] for el in buttons])
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
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
            regions_markup = get_regions_keyboard(shift_index, keys)
            regions_markup.inline_keyboard.insert(-1, [InlineKeyboardButton(text="📋 Все списки", callback_data=f"spiski_all:{shift_index}")])
            await callback.message.answer(text, parse_mode="HTML", reply_markup=regions_markup)
        elif len(data) == 3:
            district_index = int(data[2])
            text = f'😸 <b>Прошедшие на образовательное направление "{keys[district_index]}</b>":\n\n'
            for person in spiski[keys[district_index]]: # pyright: ignore[reportOptionalSubscript]
                line = " ".join((person["surname"], person["name"], person["patronymic"]))
                if user := get_user_by_name(person["name"], person["surname"]):
                    if user["username"]:
                        line = f'<a href="https://t.me/{html.escape(user["username"])}">{html.escape(line)}</a>'
                    elif user["id"]:
                        line = f'<a href="tg://user?id={html.escape(str(user["id"]))}">{html.escape(line)}</a>'
                line += "\n"
                text += line
            await callback.message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=get_back_markup(f"shift-info:{shift_index}"))
    await callback.answer()


@schedule_router.callback_query(F.data.startswith("spiski_all:"))
async def show_spiski_all(callback: CallbackQuery):
    if callback.data and callback.message:
        shift_index = int(callback.data.split(":")[1])
        name = get_old_data()[shift_index]["name"]
        spiski_data = get_spiski(name)
        if not spiski_data:
            await callback.answer()
            return
        keys = sorted(spiski_data.keys())

        for district_key in keys:
            text = f'😸 <b>Прошедшие на образовательное направление "{district_key}</b>":\n\n'
            for person in spiski_data[district_key]:
                line = " ".join((person["surname"], person["name"], person["patronymic"]))
                if user := get_user_by_name(person["name"], person["surname"]):
                    if user["username"]:
                        line = f'<a href="https://t.me/{html.escape(user["username"])}">{html.escape(line)}</a>'
                    elif user["id"]:
                        line = f'<a href="tg://user?id={html.escape(str(user["id"]))}">{html.escape(line)}</a>'
                text += line + "\n"

            await callback.message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=get_back_markup(f"shift-info:{shift_index}"))
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
        markup.append([InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats:{shift_index}")])
        markup.append([InlineKeyboardButton(text="🔙 Назад", callback_data="schedule")])
        markup = InlineKeyboardMarkup(inline_keyboard=markup)
        await callback.message.answer(
            text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup
        )
    await callback.answer()


@schedule_router.callback_query(F.data.startswith("stats:"))
async def show_stats(callback: CallbackQuery):
    if not callback.data or not callback.message:
        return
    shift_index = int(callback.data.split(":")[1])
    shifts = get_old_data()
    if shift_index >= len(shifts):
        return
    shift = shifts[shift_index]
    name = shift["name"]

    dopusheni_data = get_dopusheni(name)
    if not dopusheni_data:
        text = f"📊 <b>{name}</b>\n\nСписок допущенных ещё не загружен."
    else:
        regions = sorted(dopusheni_data.keys())
        total = sum(len(persons) for persons in dopusheni_data.values())
        text = f"📊 <b>{name}</b>\n\n📋 <b>Допущенные ко второму этапу:</b>\n  Всего: {total}\n\n  <b>По регионам:</b>\n"
        for region in regions:
            count = len(dopusheni_data[region])
            text += f"    {region}: {count}\n"
        text += "\n"

        from tools.competition import get_competition, get_competition_status
        comp = get_competition(name)
        if comp:
            text += f"📈 <b>Средний конкурс:</b> {comp['overall']} чел/место\n\n"
            text += "<b>По направлениям <i>(относительно среднего конкурса)</i>:</b>\n"
            for direction, competition in comp["per_direction"].items():
                text += f"  {direction} — {get_competition_status(comp['overall'], competition)}\n"
            text += f"\n🆕 Первашей: ~{comp['new_count']}"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск по спискам", callback_data=f"search:{shift_index}")],
        [get_back_button(f"shift-info:{shift_index}")],
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()
