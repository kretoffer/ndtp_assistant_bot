from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command
from database import get_db_connection, check_username

import logging

from config import Config
from keyboards.subscriptions_keyboards import get_subscription_keyboard

subscriptions_router = Router()


@subscriptions_router.message(Command("subscriptions"))
async def cmd_subscriptions(message: Message, config: Config):
    if not message.from_user:
        return

    check_username(message.from_user.id, message.from_user.username)

    keyboard = get_subscription_keyboard(message.from_user.id, config.TOPIC_NAMES)
    if keyboard:
        await message.answer(config.messages.subscriptions, reply_markup=keyboard, parse_mode="HTML")
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO subscriptions (id) VALUES (?)",
            (message.from_user.id,),
        )
        conn.commit()
        keyboard = get_subscription_keyboard(message.from_user.id, config.TOPIC_NAMES)
        await message.answer("Управление вашими подписками:", reply_markup=keyboard)


@subscriptions_router.callback_query(F.data.startswith("toggle_subscription:"))
async def toggle_subscription_handler(callback_query: CallbackQuery, config: Config):
    if not callback_query.message or not callback_query.from_user:
        return

    check_username(callback_query.from_user.id, callback_query.from_user.username)

    topic = callback_query.data.split(":")[1] # pyright: ignore[reportOptionalMemberAccess]

    if topic not in config.TOPIC_NAMES:
        await callback_query.answer(f"{config.messages.error_occured}. Неизвестный тип подписки.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT {topic} FROM subscriptions WHERE id = ?", (callback_query.from_user.id,))
        current_state = cursor.fetchone()

        if current_state is None:
            await callback_query.answer(f"{config.messages.error_occured}. Профиль подписок не найден.", show_alert=True)
            return

        new_state = not current_state[topic]

        cursor.execute(
            f"UPDATE subscriptions SET {topic} = ? WHERE id = ?",
            (new_state, callback_query.from_user.id),
        )
        conn.commit()

        new_keyboard = get_subscription_keyboard(callback_query.from_user.id, config.TOPIC_NAMES)
        if isinstance(callback_query.message, InaccessibleMessage):
            await callback_query.answer()
            return
        await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)
        await callback_query.answer(f"Статус подписки '{config.TOPIC_NAMES[topic]}' изменен.")

    except Exception as e:
        await callback_query.answer(config.messages.error_occured, show_alert=True)
        logging.error(f"An error occurred: {e}")
