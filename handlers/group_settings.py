import logging
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command

from config import Config
from database import toggle_group_setting
from keyboards.group_settings_keyboard import get_group_settings_keyboard

from tools.group_tools import is_admin, is_bot_admin

logger = logging.getLogger(__name__)

group_settings_router = Router()


@group_settings_router.message(Command("group_settings"))
async def cmd_group_settings(message: Message, bot: Bot, config: Config):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Эта команда работает только в группах.")
        return

    if not message.from_user:
        return

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


@group_settings_router.callback_query(F.data.startswith("toggle_group_setting:"))
async def toggle_group_setting_handler(callback_query: CallbackQuery, bot: Bot, config: Config):
    if not callback_query.message or not callback_query.from_user:
        return

    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if not await is_admin(bot, chat_id, user_id):
        await callback_query.answer("❌ Только администраторы могут менять настройки.", show_alert=True)
        return

    data = callback_query.data
    if not data:
        await callback_query.answer()
        return
    setting = data.split(":", 1)[1]

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

    except Exception as e:
        logger.error(f"Error toggling group setting: {e}")
        await callback_query.answer("Произошла ошибка.", show_alert=True)
