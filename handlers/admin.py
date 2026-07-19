import asyncio
import html
import logging
from typing import Union

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, InaccessibleMessage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import get_db_connection
from keyboards import get_back_markup
from tools import get_from_user_and_answer_from_update

admin_logger = logging.getLogger("admin")
admin_router = Router()

USERS_PER_PAGE = 15
MAX_OUTPUT_LENGTH = 3500
MAX_COLUMN_WIDTH = 40
SQL_FETCH_LIMIT = 101


class AdminSQL(StatesGroup):
    waiting_for_query = State()


async def _is_admin(update: Union[Message, CallbackQuery], config: Config) -> bool:
    if isinstance(update, CallbackQuery):
        if not update.message or isinstance(update.message, InaccessibleMessage):
            return False
        if update.from_user.id != config.admin_id:
            await update.message.edit_text(config.messages.fallback_message)
            await update.message.answer(config.messages.start_phrase)
            return False
        return True
    if isinstance(update, Message):
        if not update.from_user:
            return False
        if update.from_user.id != config.admin_id:
            await update.answer(config.messages.fallback_message)
            await update.answer(config.messages.start_phrase)
            return False
        return True
    return False


def _admin_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🗄 SQL запрос", callback_data="admin:sql")],
        [InlineKeyboardButton(text="📋 Юзеры (1)", callback_data="admin:users:0")],
        [InlineKeyboardButton(text="🔙 Закрыть", callback_data="home")],
    ])


def _format_sql_result(rows: list, columns: list[str]) -> str:
    if not rows:
        return "✅ Запрос выполнен."
    if not columns:
        return f"✅ Запрос выполнен. {len(rows)} строк."

    lines = []
    lines.append(" | ".join(f"<b>{html.escape(c)}</b>" for c in columns))
    lines.append("—" * min(60, len(columns) * 20))

    for row in rows[:20]:
        vals = []
        for v in row:
            s = str(v) if v is not None else "NULL"
            if len(s) > MAX_COLUMN_WIDTH:
                s = s[:MAX_COLUMN_WIDTH - 3] + "..."
            vals.append(html.escape(s))
        lines.append(" | ".join(vals))

    text = "\n".join(lines)
    if len(rows) > 20:
        text += f"\n\n<i>... и ещё {len(rows) - 20} строк</i>"
    if len(text) > MAX_OUTPUT_LENGTH:
        text = text[:MAX_OUTPUT_LENGTH] + "\n\n<i>... вывод обрезан</i>"
    return text


def _users_markup(page: int, total: int) -> InlineKeyboardMarkup:
    if total == 0:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Панель", callback_data="admin")],
        ])

    pages = (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="←", callback_data=f"admin:users:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="admin:noop"))
    if page < pages - 1:
        row.append(InlineKeyboardButton(text="→", callback_data=f"admin:users:{page + 1}"))

    buttons = [row]
    buttons.append([InlineKeyboardButton(text="🔙 Панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _log(admin_id: int, action: str) -> None:
    admin_logger.info(f"Admin {admin_id}: {action}")


@admin_router.message(Command("admin"))
@admin_router.callback_query(lambda c: c.data == "admin")
async def cmd_admin(update: Union[Message, CallbackQuery], config: Config):
    if not await _is_admin(update, config):
        return
    from_user, answer = get_from_user_and_answer_from_update(update)
    if not from_user or not answer:
        return
    _log(from_user.id, "открыл админ панель")
    await answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=_admin_markup())


@admin_router.callback_query(F.data.startswith("admin:stats"))
async def admin_stats(callback: CallbackQuery, config: Config):
    if not await _is_admin(callback, config):
        return
    message = callback.message
    if not message or isinstance(message, InaccessibleMessage):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM groups")
    total_groups = cursor.fetchone()[0]

    lines = [f"📊 <b>Статистика БД</b>\n\nВсего пользователей: <b>{total_users}</b>\nВсего групп: <b>{total_groups}</b>\n"]
    cursor.execute("PRAGMA table_info(subscriptions)")
    columns = [row[1] for row in cursor.fetchall()]
    skip = {"id", "directions"}
    for col in columns:
        if col in skip:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM subscriptions WHERE {col} = 1")
        count = cursor.fetchone()[0]
        lines.append(f"  {col}: {count}")

    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Панель", callback_data="admin")],
    ])
    await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    _log(callback.from_user.id, "просмотр статистики БД")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:users:"))
async def admin_users(callback: CallbackQuery, config: Config):
    if not await _is_admin(callback, config):
        return
    message = callback.message
    if not message or isinstance(message, InaccessibleMessage):
        return
    if not callback.data:
        return

    data = callback.data.split(":")
    try:
        page = int(data[2])
    except (ValueError, IndexError):
        await callback.answer()
        return
    if page < 0:
        page = 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT id, name, surname, username FROM users ORDER BY id LIMIT ? OFFSET ?",
        (USERS_PER_PAGE, page * USERS_PER_PAGE),
    )
    rows = cursor.fetchall()

    lines = [f"📋 <b>Пользователи</b> (всего {total})\n"]
    for row in rows:
        parts = [f"<code>{row['id']}</code>"]
        if row["surname"] or row["name"]:
            name = " ".join(filter(None, (row["surname"], row["name"])))
            parts.append(html.escape(name))
        if row["username"]:
            parts.append(f"@{html.escape(row['username'])}")
        lines.append("  • " + " — ".join(parts))

    text = "\n".join(lines)
    await message.edit_text(text, parse_mode="HTML", reply_markup=_users_markup(page, total))
    _log(callback.from_user.id, f"просмотр юзеров (стр. {page + 1})")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:noop"))
async def admin_noop(callback: CallbackQuery):
    await callback.answer()


@admin_router.callback_query(F.data == "admin:sql")
async def admin_sql_start(callback: CallbackQuery, state: FSMContext, config: Config):
    if not await _is_admin(callback, config):
        return
    message = callback.message
    if not message or isinstance(message, InaccessibleMessage):
        return

    await message.edit_text(
        "🗄 Введите SQL запрос\n\n"
        "Например: <code>SELECT id, username FROM users LIMIT 5</code>",
        parse_mode="HTML",
        reply_markup=get_back_markup("admin"),
    )
    await state.set_state(AdminSQL.waiting_for_query)
    _log(callback.from_user.id, "открыл ввод SQL")
    await callback.answer()


@admin_router.message(Command("sql"))
async def cmd_sql(message: Message, config: Config):
    if not await _is_admin(message, config):
        return
    text = message.text or ""
    query = text.removeprefix("/sql ").strip()
    if not query:
        await message.answer("Укажите запрос. Например: <code>/sql SELECT * FROM users</code>", parse_mode="HTML")
        return
    await _execute_sql(message, query, config.admin_id)


@admin_router.message(AdminSQL.waiting_for_query)
async def admin_sql_execute(message: Message, state: FSMContext, config: Config):
    if not await _is_admin(message, config):
        return
    if not message.text:
        return
    query = message.text.strip()
    await _execute_sql(message, query, config.admin_id)
    await state.clear()


def _execute_sql_sync(query: str) -> tuple:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT") or query_upper.startswith("PRAGMA"):
            columns = [desc[0] for desc in (cursor.description or [])]
            rows = cursor.fetchmany(SQL_FETCH_LIMIT)
            return columns, rows, None, True
        else:
            conn.commit()
            return None, None, cursor.rowcount, False
    except Exception:
        conn.rollback()
        raise


async def _execute_sql(msg: Message, query: str, admin_id: int):
    try:
        columns, rows, affected, is_select = await asyncio.to_thread(_execute_sql_sync, query)
        if is_select:
            text = _format_sql_result(rows, columns)
            await msg.answer(text, parse_mode="HTML")
            _log(admin_id, f"SQL SELECT ({len(rows)} rows)")
        else:
            await msg.answer(f"✅ Затронуто строк: {affected}")
            _log(admin_id, f"SQL WRITE ({affected} rows affected)")
    except Exception as e:
        await msg.answer(f"❌ <b>Ошибка:</b> {html.escape(str(e))}", parse_mode="HTML")
        _log(admin_id, "SQL ERROR")
