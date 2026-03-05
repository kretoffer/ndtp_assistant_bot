import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from database import get_db_connection, init_db, close_db_connection
from handlers import (
    start_router
    )

logging.basicConfig(level=logging.INFO)

async def on_startup(dispatcher: Dispatcher):
    get_db_connection(dispatcher['config'].db_path)
    init_db()

async def on_shutdown(dispatcher: Dispatcher):
    close_db_connection()

async def main():
    config = load_config()

    storage = MemoryStorage()

    bot = Bot(token=config.token)
    dp = Dispatcher(storage=storage, config=config)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(start_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())