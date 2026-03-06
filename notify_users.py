import logging
import html
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database import get_all_users


def generate_message_text(changes):
    text = "<b>Изменение календаря образовательных смен:</b>"
    if changes["removed_shifts"]:
        text += "\n\n<b>Удалены смены:</b>"
        for removed_shift in changes["removed_shifts"]:
            text += "\n" + html.escape(removed_shift["name"])
    if changes["new_shifts"]:
        text += "\n\n<b>Добавлены новые смены:</b>"
        for new_shift in changes["new_shifts"]:
            text += "\n" + html.escape(new_shift["name"])
    if changes["modified_shifts"]:
        text += "\n\n<b>Изменены смены:</b>"
        for modified_shift in changes["modified_shifts"]:
            text += "\n" + html.escape(modified_shift["name"]) + ":\n"
            modifications = modified_shift["changes"]
            if "date" in modifications:
                text += f" - Изменены даты проведения:\n  С: {html.escape(modifications['date']['from'])}\n  На: {html.escape(modifications['date']['to'])}\n"
            if "feed" in modifications:
                text += f" - Изменены даты подачи:\n  С: {html.escape(modifications['feed']['from'])}\n  На: {html.escape(modifications['feed']['to'])}\n"
            if "removed_docs" in modifications:
                text += " - Удалены документы:\n"
                for name, file_link in modifications["removed_docs"].items():
                    text += f"<s>{html.escape(name)}</s>\n"
            if "added_docs" in modifications:
                text += " - Добавлены документы:\n"
                for name, file_link in modifications["added_docs"].items():
                    text += f'<a href="{html.escape(file_link)}">{html.escape(name)}</a>\n'
    return text


async def notify_all_users(bot: Bot, changes):
    users = get_all_users()
    text = generate_message_text(changes)
    logging.info(f"Starting to send message to {len(users)} users.")

    for user in users:
        user_id = user['id']
        try:
            await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
        except TelegramForbiddenError:
            logging.warning(f"User {user_id} has blocked the bot. Cannot send message.")
        except TelegramBadRequest as e:
            logging.error(f"Failed to send message to user {user_id}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while sending message to user {user_id}: {e}")

    logging.info("Finished sending messages to all users.")
