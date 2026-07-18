from typing import Union

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import html

from keyboards.schedule_keyboards import get_schedule_keyboard, get_regions_keyboard
from keyboards import get_back_button, get_back_markup
from keyboards.cancel_keyboard import cancel_keyboard
from parser import get_old_data, get_districts, get_spiski, get_dopusheni, get_districts_info
from database import get_user_by_name, check_username, add_user

from tools import get_from_user_and_answer_from_update
from tools.search import search_persons
from tools.search_cache import store as _store_search, get as _get_search


schedule_router = Router()

PAGE_SIZE = 10


class SearchState(StatesGroup):
    waiting_for_query = State()


def _format_person_line(person: dict) -> str:
    line = " ".join(((person.get("surname") or ""), (person.get("name") or ""), (person.get("patronymic") or "")))
    if user := get_user_by_name(person["name"], person["surname"]):
        if user["username"]:
            line = f'<a href="https://t.me/{html.escape(user["username"])}">{html.escape(line)}</a>'
        elif user["id"]:
            line = f'<a href="tg://user?id={html.escape(str(user["id"]))}">{html.escape(line)}</a>'
    return html.escape(line) if line == html.escape(line) else line


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
        districts_names = list(districts_info.keys()) # pyright: ignore[reportOptionalMemberAccess]
        buttons = []
        if programs:
            for district, program in programs.items():
                if district in districts_names:
                    programs_names = list(districts_info[district]["programs"].keys()) # pyright: ignore[reportOptionalSubscript]
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
            markup = get_regions_keyboard(shift_index, keys)
            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
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

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск по спискам", callback_data=f"search:{shift_index}")],
        [get_back_button(f"shift-info:{shift_index}")],
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@schedule_router.callback_query(F.data.startswith("search:"))
async def start_search(callback: CallbackQuery, state: FSMContext):
    if not callback.data or not callback.message:
        return
    shift_index = int(callback.data.split(":")[1])
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(shift_index=shift_index)
    await callback.message.answer(
        "🔍 Введите фамилию, имя, отчество или учреждение образования для поиска\n\n"
        "Поиск идёт по спискам <b>допущенных</b> и <b>прошедших</b>.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@schedule_router.message(SearchState.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    if not message.from_user or not message.text:
        return
    check_username(message.from_user.id, message.from_user.username)

    state_data = await state.get_data()
    shift_index = state_data.get("shift_index")
    if shift_index is None:
        await state.clear()
        return

    shifts = get_old_data()
    if shift_index >= len(shifts):
        await state.clear()
        return
    shift_name = shifts[shift_index]["name"]

    query = message.text.strip()
    if not query:
        await message.answer("Введите хотя бы один символ для поиска.", reply_markup=cancel_keyboard)
        return

    results, total = search_persons(query, shift_name=shift_name, lists="all")

    if total == 0:
        await message.answer(f"🔍 По запросу «{html.escape(query)}» ничего не найдено.")
        await state.clear()
        return

    _store_search(message.from_user.id, shift_index, query, results, total)

    page = 0
    chunk = results[:PAGE_SIZE]
    text = _build_search_results_text(query, total, chunk, page)
    markup = _build_search_pagination_markup(shift_index, total, page)

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await state.clear()


@schedule_router.callback_query(F.data.startswith("search_page:"))
async def search_page_handler(callback: CallbackQuery):
    if not callback.data or not callback.message:
        return
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    entry = _get_search(user_id)
    if not entry:
        await callback.message.answer("Результаты поиска устарели. Начните поиск заново.")
        await callback.answer()
        return

    total = entry["total"]
    shift_index = entry["shift_index"]
    query = entry["query"]
    start = page * PAGE_SIZE
    chunk = entry["results"][start:start + PAGE_SIZE]

    text = _build_search_results_text(query, total, chunk, page)
    markup = _build_search_pagination_markup(shift_index, total, page)

    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup) # pyright: ignore[reportAttributeAccessIssue]
    await callback.answer()


def _build_search_results_text(query: str, total: int, chunk: list[dict], page: int) -> str:
    parts = []
    dopusheni_results = [r for r in chunk if r["list_type"] == "dopusheni"]
    spiski_results = [r for r in chunk if r["list_type"] == "spiski"]

    if dopusheni_results:
        parts.append(f"📋 <b>Допущенные ({len(dopusheni_results)}):</b>")
        for r in dopusheni_results:
            p = r["person"]
            line = _format_person_line(p)
            education = html.escape(p.get("education") or "")
            parts.append(f"  • {line} — <i>{html.escape(r['region'])}, {education}</i>")
        parts.append("")

    if spiski_results:
        parts.append(f"👀 <b>Прошедшие ({len(spiski_results)}):</b>")
        for r in spiski_results:
            p = r["person"]
            line = _format_person_line(p)
            education = html.escape(p.get("education") or "")
            parts.append(f"  • {line} — <i>{html.escape(r['region'])}, {education}</i>")
        parts.append("")

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    text = f"🔍 Результаты поиска «{html.escape(query)}» (найдено {total}):\n\n"
    text += "\n".join(parts)
    text += f"\nСтр. {page + 1}/{pages}"
    return text


def _build_search_pagination_markup(shift_index: int, total: int, current_page: int) -> InlineKeyboardMarkup:
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    row = []
    if current_page > 0:
        row.append(InlineKeyboardButton(text="← Назад", callback_data=f"search_page:{current_page - 1}"))
    if current_page < pages - 1:
        row.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"search_page:{current_page + 1}"))

    buttons = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="📊 К статистике", callback_data=f"stats:{shift_index}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
