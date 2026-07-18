import re
import logging
from datetime import date, timedelta

import html

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from parser import get_old_data
from database import get_subscribers_by_topic

logger = logging.getLogger(__name__)


def parse_feed_dates(feed_text: str) -> tuple[date, date] | None:
    pattern = r"с\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s+по\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s*г?\.?"
    match = re.search(pattern, feed_text.strip())
    if not match:
        return None

    d1, m1, y1, d2, m2, y2 = match.groups()
    if y1 is None:
        y1 = y2

    return (
        date(int(y1), int(m1), int(d1)),
        date(int(y2), int(m2), int(d2)),
    )


async def check_and_send_reminders(bot: Bot):
    today = date.today()

    for shift in get_old_data():
        dates = parse_feed_dates(shift.get("feed", ""))
        if not dates:
            continue

        start, end = dates
        name = shift["name"]

        if today == start:
            text = (
                f"📅 Сегодня, {start.strftime('%d.%m')}, "
                f"открывается приём заявок на смену «{html.escape(name)}»"
            )
            await _send(bot, text)

        if today == end - timedelta(days=1):
            text = (
                f"⚠️ Завтра, {end.strftime('%d.%m')}, "
                f"последний день подачи заявок на смену «{html.escape(name)}»"
            )
            await _send(bot, text)


async def _send(bot: Bot, text: str):
    subscribers = get_subscribers_by_topic("application_reminders")
    for user in subscribers:
        user_id = user["id"]
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
        except TelegramForbiddenError:
            logger.warning(f"User {user_id} blocked the bot")
        except TelegramBadRequest as e:
            logger.error(f"Failed to send to {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending to {user_id}: {e}")
