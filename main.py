import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from handlers import (
    start_router
    )

logging.basicConfig(level=logging.INFO)

async def main():
    config = load_config()

    storage = MemoryStorage()

    bot = Bot(token=config.token)
    dp = Dispatcher(storage=storage, config=config)

    dp.include_router(start_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())