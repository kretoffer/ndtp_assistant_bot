import logging
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, ChatMemberUpdated

from database import add_group, remove_group
from tools.group_tools import is_bot_admin
from config import Config

logger = logging.getLogger(__name__)

group_managment_router = Router()


@group_managment_router.message(F.new_chat_members)
async def on_group_join(message: Message, bot: Bot, config: Config):
    if not message.new_chat_members:
        return
    for member in message.new_chat_members:
        if member.id == bot.id:
            group_id = message.chat.id
            add_group(group_id)
            logger.info(f"Bot was added to group {group_id}")
            features = "\n".join(f"• {name}" for name in config.GROUP_SETTINGS.values())
            text = (
                "Спасибо за добавление в группу! "
                "Я буду присылать сюда уведомления об изменениях в календаре образовательных смен.\n\n"
                f"⚙️ <b>Доступные функции:</b>\n{features}\n\n"
                "Настроить их можно командой /group_settings"
            )
            if not is_bot_admin:
                text += (
                    "⚠️ <b>Важно:</b> Для работы некоторых функций мне нужны "
                    "права администратора в чате.\n"
                    "Выдайте мне права администратора."
                )
            await message.answer(text, parse_mode="HTML")
            break


@group_managment_router.my_chat_member()
async def on_bot_admin_change(event: ChatMemberUpdated, bot: Bot, config: Config):
    if event.chat.type not in ("group", "supergroup"):
        return

    old = event.old_chat_member.status
    new = event.new_chat_member.status

    if old == "administrator" and new != "administrator":
        features = "\n".join(f"• {name}" for name in config.GROUP_SETTINGS.values())
        text = (
            "❌ <b>Я потерял права администратора!</b>\n\n"
            "Следующие функции могут работать некорректно:\n"
            f"{features}\n\n"
            "Пожалуйста, верните мне права администратора "
            "с включённым правом «Читать сообщения»."
        )
        try:
            await bot.send_message(event.chat.id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.warning(f"Bot was kicked from group {event.chat.id}")
        except TelegramBadRequest as e:
            logger.error(f"Failed to send admin lost message to group {event.chat.id}: {e}")

    elif old != "administrator" and new == "administrator":
        text = (
            "✅ <b>Я получил права администратора!</b>\n\n"
            "Теперь вы можете настроить функции через /group_settings"
        )
        try:
            await bot.send_message(event.chat.id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.warning(f"Bot was kicked from group {event.chat.id}")
        except TelegramBadRequest as e:
            logger.error(f"Failed to send admin granted message to group {event.chat.id}: {e}")


@group_managment_router.message(F.left_chat_member)
async def on_group_leave(message: Message, bot: Bot):
    if not message.left_chat_member:
        return
    if message.left_chat_member.id == bot.id:
        group_id = message.chat.id
        remove_group(group_id)
        logger.info(f"Bot was removed from group {group_id}")
