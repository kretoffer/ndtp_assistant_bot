from aiogram import Bot
from aiogram.types import ChatMemberAdministrator


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, ChatMemberAdministrator) or member.status == "creator"
    except Exception:
        return False


async def is_bot_admin(bot: Bot, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        return isinstance(member, ChatMemberAdministrator) or member.status == "creator"
    except Exception:
        return False
