import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards import get_back_button
from keyboards.cancel_keyboard import cancel_keyboard
from parser import get_old_data
from database import get_user_by_name, check_username, add_user
from tools.search import search_persons
from tools.profile import build_profile_text
from tools.search_cache import store as _store_search, get as _get_search, update_page as _update_page


search_router = Router()

PAGE_SIZE = 10


class SearchState(StatesGroup):
    waiting_for_query = State()


def _format_person_line(person: dict) -> str:
    line = " ".join(((person.get("surname") or ""), (person.get("name") or ""), (person.get("patronymic") or "")))
    if user := get_user_by_name(person.get("name") or "", person.get("surname") or ""):
        if user["username"]:
            line = f'<a href="https://t.me/{html.escape(user["username"])}">{html.escape(line)}</a>'
        elif user["id"]:
            line = f'<a href="tg://user?id={html.escape(str(user["id"]))}">{html.escape(line)}</a>'
    return html.escape(line) if line == html.escape(line) else line


def _build_search_text(query: str, total: int, chunk: list[dict], page: int, shift_names: list[str]) -> str:
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

    distance_results = [r for r in chunk if r["list_type"] == "distance"]
    if distance_results:
        parts.append(f"📡 <b>Дистанционное обучение ({len(distance_results)}):</b>")
        for r in distance_results:
            p = r["person"]
            line = _format_person_line(p)
            direction = html.escape(p.get("direction", ""))
            project = html.escape(p.get("project", ""))
            period = html.escape(p.get("study_period") or "")
            parts.append(f"  • {line} — <i>{direction}, {project} — {period}</i>")
        parts.append("")

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    text = f"🔍 Результаты поиска «{html.escape(query)}» (найдено {total}):\n\n"
    text += "\n".join(parts)
    text += f"\nСтр. {page + 1}/{pages}"
    text += f"\n\n<i>Поиск проходил по спискам: {', '.join(html.escape(s) for s in shift_names)}</i>"
    return text


def _build_search_markup(shift_index: int | None, total: int, current_page: int, chunk: list[dict], offset: int) -> InlineKeyboardMarkup:
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    buttons = []

    for i, r in enumerate(chunk):
        idx = offset + i
        p = r["person"]
        surname = (p.get("surname") or "?")[:20]
        name_initial = (p.get("name") or "?")[0]
        buttons.append([InlineKeyboardButton(text=f"👤 {surname} {name_initial}.", callback_data=f"profile:{idx}")])

    pagination_row = []
    if current_page > 0:
        pagination_row.append(InlineKeyboardButton(text="← Назад", callback_data=f"search_page:{current_page - 1}"))
    if current_page < pages - 1:
        pagination_row.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"search_page:{current_page + 1}"))
    if pagination_row:
        buttons.append(pagination_row)

    if shift_index is not None:
        buttons.append([InlineKeyboardButton(text="📊 К статистике", callback_data=f"stats:{shift_index}")])
    else:
        buttons.append([get_back_button("home")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@search_router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    if not message.from_user:
        return
    add_user(message.from_user.id, message.from_user.username)
    check_username(message.from_user.id, message.from_user.username)

    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(shift_index=None)
    await message.answer(
        "🔍 Введите фамилию, имя, отчество или учреждение образования для поиска\n\n"
        "Поиск идёт по <b>всем сменам</b> в списках допущенных и прошедших.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )


@search_router.callback_query(F.data.startswith("search:"))
async def start_search(callback: CallbackQuery, state: FSMContext):
    if not callback.data or not callback.message:
        return
    shift_index = int(callback.data.split(":")[1])
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(shift_index=shift_index)
    await callback.message.answer(
        "🔍 Введите фамилию, имя, отчество или учреждение образования для поиска\n\n"
        "Поиск идёт по спискам <b>допущенных</b> и <b>прошедших</b> этой смены.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@search_router.message(SearchState.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    if not message.from_user or not message.text:
        return
    check_username(message.from_user.id, message.from_user.username)

    state_data = await state.get_data()
    shift_index: int | None = state_data.get("shift_index")

    query = message.text.strip()
    if not query:
        await message.answer("Введите хотя бы один символ для поиска.", reply_markup=cancel_keyboard)
        return

    shifts = get_old_data()
    if shift_index is not None:
        if shift_index >= len(shifts):
            await state.clear()
            return
        shift_name = shifts[shift_index]["name"]
        shift_names = [shift_name]
    else:
        shift_name = None
        shift_names = [s["name"] for s in shifts]

    results, total = search_persons(query, shift_name=shift_name, lists="all")

    if total == 0:
        await message.answer(f"🔍 По запросу «{html.escape(query)}» ничего не найдено.")
        await state.clear()
        return

    _store_search(message.from_user.id, shift_index, query, results, total)

    page = 0
    chunk = results[:PAGE_SIZE]
    text = _build_search_text(query, total, chunk, page, shift_names)
    markup = _build_search_markup(shift_index, total, page, chunk, 0)

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await state.clear()


@search_router.callback_query(F.data.startswith("search_page:"))
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

    _update_page(user_id, page)

    total = entry["total"]
    shift_index = entry["shift_index"]
    query = entry["query"]

    if shift_index is not None:
        shift_names = [get_old_data()[shift_index]["name"]]
    else:
        shift_names = [s["name"] for s in get_old_data()]

    start = page * PAGE_SIZE
    chunk = entry["results"][start:start + PAGE_SIZE]

    text = _build_search_text(query, total, chunk, page, shift_names)
    markup = _build_search_markup(shift_index, total, page, chunk, start)

    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup) # pyright: ignore[reportAttributeAccessIssue]
    await callback.answer()


@search_router.callback_query(F.data.startswith("profile:"))
async def profile_handler(callback: CallbackQuery):
    if not callback.data or not callback.message:
        return
    idx = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    entry = _get_search(user_id)
    if not entry:
        await callback.message.answer("Результаты поиска устарели. Начните поиск заново.")
        await callback.answer()
        return

    if idx >= len(entry["results"]):
        await callback.answer("Ошибка: результат не найден.")
        return

    result = entry["results"][idx]
    person = result["person"]
    surname = person.get("surname") or "?"
    name = person.get("name") or "?"

    shift_names = [s["name"] for s in get_old_data()]
    text = build_profile_text(surname, name)
    text += f"\n\n<i>Поиск проходил по спискам: {', '.join(html.escape(s) for s in shift_names)}</i>"
    back_page = entry.get("current_page", 0)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К результатам", callback_data=f"search_page:{back_page}")]])
    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup) # pyright: ignore[reportAttributeAccessIssue]
    await callback.answer()
