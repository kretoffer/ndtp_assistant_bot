import logging
from aiogram import Router, F
from aiogram.types import Message

from config import Config

logger = logging.getLogger(__name__)

fallback_router = Router()


@fallback_router.message(F.text)
async def handle_unknown_message(message: Message, config: Config):
    await message.answer(config.messages.fallback_message)
    await message.answer(config.messages.start_phrase)
