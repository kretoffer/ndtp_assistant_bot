from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config import Config


start_router = Router()

@start_router.message(Command("start"))
async def cmd_start(message: Message, config: Config):
    await message.answer(config.start_phrase)
