from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command
from database import (
    add_user,
    check_username,
    get_subscription_status,
    update_subscription,
)

import logging

from config import Config
from keyboards.subscriptions_keyboards import get_subscription_keyboard

subscriptions_router = Router()


@subscriptions_router.message(Command("subscriptions"))
async def cmd_subscriptions(message: Message, config: Config):
    if not message.from_user:
        return

    add_user(message.from_user.id, message.from_user.username)
    check_username(message.from_user.id, message.from_user.username)

    keyboard = get_subscription_keyboard(message.chat.id, config.TOPIC_NAMES)
    await message.answer(
        config.messages.subscriptions, reply_markup=keyboard, parse_mode="HTML"
    )


@subscriptions_router.callback_query(F.data.startswith("toggle_subscription:"))
async def toggle_subscription_handler(callback_query: CallbackQuery, config: Config):
    if not callback_query.message or not callback_query.from_user:
        return

    check_username(callback_query.from_user.id, callback_query.from_user.username)

    topic = callback_query.data.split(":")[1] # pyright: ignore[reportOptionalMemberAccess]

    if topic not in config.TOPIC_NAMES:
        await callback_query.answer(
            f"{config.messages.error_occured}. Неизвестный тип подписки.",
            show_alert=True,
        )
        return

    try:
        current_state = get_subscription_status(callback_query.message.chat.id)

        if current_state is None:
            await callback_query.answer(
                f"{config.messages.error_occured}. Профиль подписок не найден.",
                show_alert=True,
            )
            return

        new_state = not current_state[topic]

        update_subscription(callback_query.message.chat.id, topic, new_state)

        new_keyboard = get_subscription_keyboard(callback_query.message.chat.id, config.TOPIC_NAMES)
        if isinstance(callback_query.message, InaccessibleMessage):
            await callback_query.answer()
            return
        await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)
        await callback_query.answer(f"Статус подписки '{config.TOPIC_NAMES[topic]}' изменен.")

    except Exception as e:
        await callback_query.answer(config.messages.error_occured, show_alert=True)
        logging.error(f"An error occurred: {e}")
