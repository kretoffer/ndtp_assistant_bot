import html
from collections import Counter

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, InaccessibleMessage

from keyboards import get_back_button
from database import check_username, add_user
from parser.distance_parser import get_distance_students
from tools.profile import format_person_name, format_distance_block


dists_router = Router()
PAGE_SIZE = 10


def _get_dirs() -> list[str]:
    dir_counts = Counter(s["direction"] for s in get_distance_students())
    return sorted(dir_counts.keys())


def _build_main_text() -> str:
    students = get_distance_students()
    if not students:
        return "Данные дистанционного обучения ещё не загружены. Попробуйте позже."
    total = len(students)
    dir_counts = Counter(s["direction"] for s in students)
    lines = [
        "📊 <b>Дистанционная форма обучения</b>\n",
        f"Всего: {total} человек\n",
    ]
    for d in sorted(dir_counts):
        lines.append(f"  • {html.escape(d)}: {dir_counts[d]}")
    return "\n".join(lines)


def _build_main_markup() -> InlineKeyboardMarkup:
    dirs = _get_dirs()
    buttons = []
    for i, d in enumerate(dirs):
        buttons.append([InlineKeyboardButton(text=d, callback_data=f"dists_dir:{i}:0")])
    buttons.append([get_back_button("home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_dir_students(direction: str) -> list[dict]:
    return [s for s in get_distance_students() if s["direction"] == direction]


def _build_dir_text(direction: str, students: list[dict], page: int) -> str:
    total = len(students)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    chunk = students[start:start + PAGE_SIZE]

    lines = [f"📌 <b>{html.escape(direction)}</b>\n"]
    for s in chunk:
        fio = " ".join(filter(None, (s["surname"], s["name"], s["patronymic"])))
        lines.append(f"  • {html.escape(fio)}")
        if s.get("project"):
            lines.append(f"    🔬 {html.escape(s['project'][:60])}")
        lines.append(f"    🏫 {html.escape(s['school'][:50])}")
        lines.append("")
    lines.append(f"Стр. {page + 1}/{pages}")
    return "\n".join(lines)


def _build_dir_markup(dir_idx: int, students: list[dict], page: int) -> InlineKeyboardMarkup:
    total = len(students)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    chunk = students[start:start + PAGE_SIZE]
    buttons = []

    for i, s in enumerate(chunk):
        offset = start + i
        surname = (s.get("surname") or "?")[:20]
        name_initial = (s.get("name") or "?")[0]
        buttons.append([InlineKeyboardButton(
            text=f"👤 {surname} {name_initial}.",
            callback_data=f"dists_person:{dir_idx}:{offset}",
        )])

    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton(text="← Назад", callback_data=f"dists_page:{dir_idx}:{page - 1}"))
    if page < pages - 1:
        pagination_row.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"dists_page:{dir_idx}:{page + 1}"))
    if pagination_row:
        buttons.append(pagination_row)

    buttons.append([InlineKeyboardButton(text="🔙 К направлениям", callback_data="dists_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dists_router.message(Command("dists"))
async def cmd_dists(message: Message):
    if not message.from_user:
        return
    add_user(message.from_user.id, message.from_user.username)
    check_username(message.from_user.id, message.from_user.username)

    text = _build_main_text()
    markup = _build_main_markup()
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)


@dists_router.callback_query(F.data == "dists_main")
async def dists_main_handler(callback: CallbackQuery):
    if not callback.message or isinstance(callback.message, InaccessibleMessage):
        return
    text = _build_main_text()
    markup = _build_main_markup()
    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await callback.answer()


@dists_router.callback_query(F.data.startswith("dists_dir:") | F.data.startswith("dists_page:"))
async def dists_dir_handler(callback: CallbackQuery):
    if not callback.data or not callback.message or isinstance(callback.message, InaccessibleMessage):
        return
    parts = callback.data.split(":")
    dir_idx = int(parts[1])
    page = int(parts[2])
    dirs = _get_dirs()
    if dir_idx < len(dirs):
        direction = dirs[dir_idx]
        students = _get_dir_students(direction)
        if students:
            text = _build_dir_text(direction, students, page)
            markup = _build_dir_markup(dir_idx, students, page)
            await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await callback.answer()


@dists_router.callback_query(F.data.startswith("dists_person:"))
async def dists_person_handler(callback: CallbackQuery):
    if not callback.data or not callback.message or isinstance(callback.message, InaccessibleMessage):
        return
    parts = callback.data.split(":")
    dir_idx = int(parts[1])
    offset = int(parts[2])

    dirs = _get_dirs()
    if dir_idx >= len(dirs):
        await callback.answer("Направление не найдено.")
        return

    direction = dirs[dir_idx]
    students = _get_dir_students(direction)
    if offset >= len(students):
        await callback.answer("Студент не найден.")
        return

    s = students[offset]
    page = offset // PAGE_SIZE

    name_line = format_person_name(
        s.get("surname", ""), s.get("name", ""), s.get("patronymic", ""),
    )
    lines = [name_line, "", format_distance_block([s])]

    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К списку", callback_data=f"dists_dir:{dir_idx}:{page}")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    await callback.answer()
