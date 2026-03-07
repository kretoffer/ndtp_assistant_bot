import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import get_db_connection, init_db, close_db_connection
from handlers import (
    start_router,
    schedule_router
)

from parser import init_parser, parse_and_compare

logging.basicConfig(level=logging.INFO)


async def on_startup(dispatcher: Dispatcher):
    get_db_connection(dispatcher["config"].db_path)
    init_db()
    await init_parser(
        dispatcher["config"].old_data_path,
        dispatcher["config"].districts_data_path,
        dispatcher["config"].dopusheni_data_path,
        dispatcher["config"].spiski_data_path
    )


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
    dp.include_router(schedule_router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        parse_and_compare, "interval", args=(bot,), seconds=config.parsing_interval
    )
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
