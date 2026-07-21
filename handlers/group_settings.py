import asyncio
import html
import logging
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InaccessibleMessage, User
from aiogram.filters import Command

from config import Config
from database import toggle_group_setting, set_group_shift, get_group_settings, get_all_groups
from keyboards.group_settings_keyboard import (
    get_group_settings_keyboard,
    get_shift_selection_keyboard,
    get_group_selection_keyboard,
)

from tools.group_tools import is_admin, is_bot_admin
from parser import get_old_data

logger = logging.getLogger(__name__)

group_settings_router = Router()


def _user_ref(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    name = html.escape(user.first_name or user.full_name or str(user.id))
    return f'<a href="tg://user?id={user.id}">{name}</a>'


@group_settings_router.message(Command("group_settings"))
async def cmd_group_settings(message: Message, bot: Bot, config: Config):
    if not message.from_user:
        return

    if message.chat.type in ("group", "supergroup"):
        if not await is_admin(bot, message.chat.id, message.from_user.id):
            await message.answer("Только администраторы группы могут менять настройки.")
            return

        admin_status = "✅ Администратор" if await is_bot_admin(bot, message.chat.id) else "❌ Не администратор"
        keyboard = get_group_settings_keyboard(message.chat.id, config.GROUP_SETTINGS)
        text = (
            f"⚙️ <b>Настройки группы</b>\n\n"
            f"🤖 Статус бота: {admin_status}\n"
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return

    all_groups = get_all_groups()
    if not all_groups:
        await message.answer("Бот не добавлен ни в одну группу.")
        return

    results = await asyncio.gather(
        *(is_admin(bot, gid, message.from_user.id) for gid in all_groups),
        return_exceptions=True,
    )

    admin_ids = [gid for gid, res in zip(all_groups, results) if res is True]

    if not admin_ids:
        await message.answer("Вы не являетесь администратором ни одной группы, где есть бот.")
        return

    chats = await asyncio.gather(
        *(bot.get_chat(gid) for gid in admin_ids),
        return_exceptions=True,
    )

    groups = []
    for gid, chat in zip(admin_ids, chats):
        if not isinstance(chat, BaseException):
            groups.append((gid, chat.title or str(gid)))

    if not groups:
        await message.answer("Не удалось получить список групп.")
        return

    keyboard = get_group_selection_keyboard(groups)
    await message.answer("Выберите группу для настройки:", reply_markup=keyboard)


@group_settings_router.callback_query(F.data.startswith("gs_select_group:"))
async def select_group_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    group_id = int(callback_query.data.split(":", 1)[1])

    if not await is_admin(bot, group_id, callback_query.from_user.id):
        await callback_query.answer("❌ Вы больше не администратор этой группы.", show_alert=True)
        return

    admin_status = "✅ Администратор" if await is_bot_admin(bot, group_id) else "❌ Не администратор"
    keyboard = get_group_settings_keyboard(group_id, config.GROUP_SETTINGS)
    text = (
        f"⚙️ <b>Настройки группы</b>\n\n"
        f"🤖 Статус бота: {admin_status}\n"
    )

    if isinstance(callback_query.message, InaccessibleMessage):
        await callback_query.answer()
        return
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback_query.answer()


@group_settings_router.callback_query(F.data.startswith("gs_toggle:"))
async def toggle_group_setting_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("Ошибка.", show_alert=True)
        return
    chat_id = int(parts[1])
    setting = parts[2]
    user_id = callback_query.from_user.id

    if not await is_admin(bot, chat_id, user_id):
        await callback_query.answer("❌ Только администраторы могут менять настройки.", show_alert=True)
        return

    if setting not in config.GROUP_SETTINGS:
        await callback_query.answer("Неизвестная настройка.", show_alert=True)
        return

    try:
        new_value = toggle_group_setting(chat_id, setting)
        if new_value is None:
            await callback_query.answer("Ошибка: настройка не найдена.", show_alert=True)
            return

        new_keyboard = get_group_settings_keyboard(chat_id, config.GROUP_SETTINGS)
        if isinstance(callback_query.message, InaccessibleMessage):
            await callback_query.answer()
            return
        await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)

        status = "включена ✅" if new_value else "выключена ❌"

        alert = None
        if new_value and not await is_bot_admin(bot, chat_id):
            alert = (
                "⚠️ Настройка включена, но бот не имеет прав администратора.\n"
                "Функция будет работать только после выдачи прав администратора."
            )

        if alert:
            await callback_query.message.answer(alert)
        await callback_query.answer(f"Настройка '{config.GROUP_SETTINGS[setting]}' {status}.")

        setting_name = config.GROUP_SETTINGS[setting]
        notification = (
            f"⚙️ <b>Настройки группы изменены</b>\n\n"
            f"👤 {_user_ref(callback_query.from_user)}\n"
            f"Настройка «{setting_name}» {status}."
        )
        try:
            await bot.send_message(chat_id, notification, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send notification to group {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Error toggling group setting: {e}")
        await callback_query.answer("Произошла ошибка.", show_alert=True)


@group_settings_router.callback_query(F.data.startswith("gs_select_shift:"))
async def select_shift_handler(callback_query: CallbackQuery, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    parts = callback_query.data.split(":")
    if len(parts) < 2:
        await callback_query.answer("Ошибка.", show_alert=True)
        return
    chat_id = int(parts[1])

    shifts = get_old_data()
    row = get_group_settings(chat_id)
    current_shift = row["selected_shift"] if row else None

    keyboard = get_shift_selection_keyboard(shifts, current_shift, chat_id)
    text = "🎯 <b>Выберите смену для фильтрации уведомлений</b>"

    if isinstance(callback_query.message, InaccessibleMessage):
        await callback_query.answer()
        return
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback_query.answer()


@group_settings_router.callback_query(F.data.startswith("gs_back:"))
async def back_to_group_settings_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    parts = callback_query.data.split(":")
    if len(parts) < 2:
        await callback_query.answer("Ошибка.", show_alert=True)
        return
    chat_id = int(parts[1])

    admin_status = "✅ Администратор" if await is_bot_admin(bot, chat_id) else "❌ Не администратор"
    keyboard = get_group_settings_keyboard(chat_id, config.GROUP_SETTINGS)
    text = (
        f"⚙️ <b>Настройки группы</b>\n\n"
        f"🤖 Статус бота: {admin_status}\n"
    )

    if isinstance(callback_query.message, InaccessibleMessage):
        await callback_query.answer()
        return
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback_query.answer()


@group_settings_router.callback_query(F.data.startswith("gs_set_all:"))
async def set_shift_all_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    parts = callback_query.data.split(":")
    if len(parts) < 2:
        await callback_query.answer("Ошибка.", show_alert=True)
        return
    chat_id = int(parts[1])
    user_id = callback_query.from_user.id

    if not await is_admin(bot, chat_id, user_id):
        await callback_query.answer("❌ Только администраторы могут менять настройки.", show_alert=True)
        return

    set_group_shift(chat_id, None)

    admin_status = "✅ Администратор" if await is_bot_admin(bot, chat_id) else "❌ Не администратор"
    keyboard = get_group_settings_keyboard(chat_id, config.GROUP_SETTINGS)
    text = (
        f"⚙️ <b>Настройки группы</b>\n\n"
        f"🤖 Статус бота: {admin_status}\n"
    )

    if isinstance(callback_query.message, InaccessibleMessage):
        await callback_query.answer()
        return
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback_query.answer("Уведомления будут приходить по всем сменам.")

    notification = (
        f"⚙️ <b>Настройки группы изменены</b>\n\n"
        f"👤 {_user_ref(callback_query.from_user)}\n"
        f"Фильтр смен: все смены"
    )
    try:
        await bot.send_message(chat_id, notification, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send notification to group {chat_id}: {e}")


@group_settings_router.callback_query(F.data.startswith("gs_set_idx:"))
async def set_shift_idx_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user or not callback_query.data:
        return

    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("Ошибка.", show_alert=True)
        return
    chat_id = int(parts[1])
    user_id = callback_query.from_user.id

    if not await is_admin(bot, chat_id, user_id):
        await callback_query.answer("❌ Только администраторы могут менять настройки.", show_alert=True)
        return

    try:
        idx = int(parts[2])
    except (ValueError, IndexError):
        await callback_query.answer("Ошибка.", show_alert=True)
        return

    shifts = get_old_data()
    if idx < 0 or idx >= len(shifts):
        await callback_query.answer("Смена не найдена.", show_alert=True)
        return

    shift_name = shifts[idx]["name"]
    set_group_shift(chat_id, shift_name)

    admin_status = "✅ Администратор" if await is_bot_admin(bot, chat_id) else "❌ Не администратор"
    keyboard = get_group_settings_keyboard(chat_id, config.GROUP_SETTINGS)
    text = (
        f"⚙️ <b>Настройки группы</b>\n\n"
        f"🤖 Статус бота: {admin_status}\n"
    )

    if isinstance(callback_query.message, InaccessibleMessage):
        await callback_query.answer()
        return
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback_query.answer(f"Уведомления только по смене: {shift_name}")

    notification = (
        f"⚙️ <b>Настройки группы изменены</b>\n\n"
        f"👤 {_user_ref(callback_query.from_user)}\n"
        f"Фильтр смен: {shift_name}"
    )
    try:
        await bot.send_message(chat_id, notification, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send notification to group {chat_id}: {e}")
