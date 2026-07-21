import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, InaccessibleMessage

logger = logging.getLogger(__name__)


async def safe_delete_message(message: Message | InaccessibleMessage | None) -> bool:
    if message is None:
        return False
    if isinstance(message, InaccessibleMessage):
        return False

    try:
        await message.delete()
        return True
    except TelegramBadRequest as e:
        logger.warning("Failed to delete message (chat=%s, msg_id=%s): %s", message.chat.id, message.message_id, e)
        return False
