import logging
import html

from aiogram import Router
from aiogram.types import ErrorEvent

from config import Config

router = Router()
logger = logging.getLogger(__name__)


@router.errors()
async def global_error_handler(event: ErrorEvent, config: Config):
    logger.exception("Unhandled exception in update %s", event.update.update_id)

    update_info = ""
    if event.update.message:
        msg = event.update.message
        if not msg.chat or not msg.from_user:
            return
        update_info = (
            f"Chat: {msg.chat.id} (@{msg.chat.username or 'N/A'})\n"
            f"User: {msg.from_user.id} (@{msg.from_user.username or 'N/A'})\n"
            f"Text: {msg.text or '<media>'}"
        )
    elif event.update.callback_query:
        cq = event.update.callback_query
        if not cq.message:
            return
        update_info = (
            f"Callback chat: {cq.message.chat.id}\n"
            f"User: {cq.from_user.id}\n"
            f"Data: {cq.data}"
        )
    else:
        update_info = str(event.update)

    error_text = (
        f"🚨 <b>Unhandled Error</b>\n\n"
        f"<b>Type:</b> {html.escape(type(event.exception).__name__)}\n"
        f"<b>Error:</b> {html.escape(str(event.exception))}\n\n"
        f"<b>Location:</b>\n{html.escape(update_info)}"
    )

    bot = event.update.bot
    if not bot:
        return

    try:
        await bot.send_message(
            config.admin_id,
            error_text[:4096],
            parse_mode="HTML"
        )
    except Exception:
        logger.exception("Failed to send error notification to admin")
