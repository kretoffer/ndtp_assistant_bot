import logging
from aiogram import Bot, F, Router
from aiogram.types import Message

from database import add_group, remove_group

logger = logging.getLogger(__name__)

group_managment_router = Router()


@group_managment_router.message(F.new_chat_members)
async def on_group_join(message: Message, bot: Bot):
    if not message.new_chat_members:
        return
    for member in message.new_chat_members:
        if member.id == bot.id:
            group_id = message.chat.id
            add_group(group_id)
            logger.info(f"Bot was added to group {group_id}")
            await message.answer(
                "Спасибо за добавление в группу! "\
                "Я буду присылать сюда уведомления об изменениях в календаре образовательных смен"
            )
            break


@group_managment_router.message(F.left_chat_member)
async def on_group_leave(message: Message, bot: Bot):
    if not message.left_chat_member:
        return
    if message.left_chat_member.id == bot.id:
        group_id = message.chat.id
        remove_group(group_id)
        logger.info(f"Bot was removed from group {group_id}")
