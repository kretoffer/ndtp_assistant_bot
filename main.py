import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import get_db_connection, init_db, close_db_connection
from handlers import (
    start_router,
    schedule_router,
    search_router,
    subscriptions_router,
    group_managment_router,
    districts_router,
    broadcast_router,
    fallback_router
)

from parser import init_parser, parse_and_compare
from parser.districts_info_parser import parse_and_compare_districts
from tools.search_cache import setup as setup_search_cache, cleanup_expired
from tools.feed_reminder import check_and_send_reminders
from logger import setup_logging

logger = logging.getLogger(__name__)


async def on_startup(dispatcher: Dispatcher):
    get_db_connection(dispatcher["config"].db_path)
    init_db(topic_names=dispatcher["config"].TOPIC_NAMES)
    setup_search_cache(dispatcher["config"].search_cache_ttl)
    await init_parser(
        dispatcher["config"].old_data_path,
        dispatcher["config"].districts_data_path,
        dispatcher["config"].dopusheni_data_path,
        dispatcher["config"].spiski_data_path,
        dispatcher["config"].districts_info_path
    )


async def on_shutdown(dispatcher: Dispatcher):
    close_db_connection()


async def main():
    config = load_config()
    setup_logging(config.log_path)

    storage = MemoryStorage()

    bot = Bot(token=config.token)
    dp = Dispatcher(storage=storage, config=config)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(start_router)
    dp.include_router(schedule_router)
    dp.include_router(search_router)
    dp.include_router(subscriptions_router)
    dp.include_router(group_managment_router)
    dp.include_router(districts_router)
    dp.include_router(broadcast_router)
    dp.include_router(fallback_router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        parse_and_compare, "interval", args=(bot,), seconds=config.parsing_interval
    )
    scheduler.add_job(
        parse_and_compare_districts, "interval", args=(bot,), seconds=config.districts_parsing_interval
    )
    scheduler.add_job(
        cleanup_expired, "interval", seconds=config.search_cache_cleanup_interval
    )
    scheduler.add_job(
        check_and_send_reminders, "cron", args=(bot,), hour=12
    )
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
