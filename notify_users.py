import logging
import html
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database import get_subscribers_by_topic, get_all_users, get_user_id_by_name, get_user_id_by_surname

DOC_NAME = "Положение об образовательной смене"
SPISKI_DOPUSCHENNYH_START_WITH = "Списочный состав участников, допущенных ко второму этапу"
SPISKI_START_WITH = "Списочный состав групп учащихся, зачисленных"
MESTA = "Места проведения"


def generate_message_text(changes):
    text = "✒️ <b>Изменение календаря образовательных смен:</b>"
    if changes["removed_shifts"]:
        text += "\n\n🗑 <b>Удалены смены:</b>"
        for removed_shift in changes["removed_shifts"]:
            text += "\n" + html.escape(removed_shift["name"])
    if changes["new_shifts"]:
        text += "\n\n📍 <b>Добавлены новые смены:</b>"
        for new_shift in changes["new_shifts"]:
            text += "\n" + html.escape(new_shift["name"])
    if changes["modified_shifts"]:
        text += "\n\n📝 <b>Изменены смены:</b>"
        for modified_shift in changes["modified_shifts"]:
            text += "\n" + html.escape(modified_shift["name"]) + ":\n"
            modifications = modified_shift["changes"]
            if "date" in modifications:
                text += f" 📆 Изменены даты проведения:\n  С: {html.escape(modifications['date']['from'])}\n  На: {html.escape(modifications['date']['to'])}\n"
            if "feed" in modifications:
                text += f" 📆 Изменены даты подачи:\n  С: {html.escape(modifications['feed']['from'])}\n  На: {html.escape(modifications['feed']['to'])}\n"
            if "removed_docs" in modifications:
                text += " 🗑 Удалены документы:\n"
                for name, file_link in modifications["removed_docs"].items():
                    text += f"<s>{html.escape(name)}</s>\n"
            if "added_docs" in modifications:
                text += " 📄 Добавлены документы:\n"
                for name, file_link in modifications["added_docs"].items():
                    text += (
                        f'<a href="{html.escape(file_link)}">{html.escape(name)}</a>\n'
                    )
            if "doc_url_changes" in modifications:
                text += " 🖇 Заменены документы:\n"
                for name, data in modifications["doc_url_changes"].items():
                    text += (
                        f'<a href="{html.escape(data['to'])}">{html.escape(name)}</a>\n'
                    )
    return text


def get_users_for_docs(docs: dict) -> set:
    users = set()
    for doc in docs:
        if doc == DOC_NAME:
            users.update(get_subscribers_by_topic("polozhenie"))
        elif doc == MESTA:
            users.update(get_subscribers_by_topic("mesta_provedeniya"))
        elif doc.startswith(SPISKI_DOPUSCHENNYH_START_WITH):
            users.update(get_subscribers_by_topic("dopusheni"))
        elif doc.startswith(SPISKI_START_WITH):
            users.update(get_subscribers_by_topic("spiski"))
        else:
            users = set(get_all_users())
    return users


async def notify_about_spiski(bot: Bot, spisok_info: dict):
    from parser import parse_new_spisok, get_districts
    spisok = await parse_new_spisok(spisok_info["link"], spisok_info["shift"], spisok_info["is_spiski"])
    for district_name, district in spisok.items():
        for person in district:
            if user_id := get_user_id_by_name(person["name"], person["surname"]):
                message = f"👋 Хей, {person['surname']} {person["name"]}, нашел тебя в списках на {'поступление' if spisok_info['is_spiski'] else 'тесты'} в <b>{spisok_info['shift']}</b>\n\n{'📚 Профиль' if spisok_info["is_spiski"] else '🗺 Область'}: {district_name} "
                district_dir = get_districts(spisok_info["shift"])[district_name] # pyright: ignore[reportOptionalSubscript]
                message += f"({district_dir})" if spisok_info['is_spiski'] and district_dir != district_name else ""
            elif user_id := get_user_id_by_surname(person["surname"]):
                message = f"👋 Хей, нашел фамилию {person['surname']} в списках на {'поступление' if spisok_info['is_spiski'] else 'тесты'} в <b>{spisok_info['shift']}</b>\n\n{'📚 Профиль' if spisok_info["is_spiski"] else '🗺 Область'}: {district_name}"
            if user_id:
                await bot.send_message(user_id, message, parse_mode="HTML") # pyright: ignore[reportPossiblyUnboundVariable]


async def notify_all_users(bot: Bot, changes, new_spiski):
    users = set()
    if changes["removed_shifts"] or changes["new_shifts"]:
        users.update(get_subscribers_by_topic("new_removed_shifts"))
    for modified_shift in changes["modified_shifts"]:
        if "date" in modified_shift["changes"] or "feed" in modified_shift["changes"]:
            users.update(get_subscribers_by_topic("dates"))
        if "removed_docs" in modified_shift["changes"]:
            users.update(get_users_for_docs(modified_shift["changes"]["removed_docs"]))
        if "added_docs" in modified_shift["changes"]:
            users.update(get_users_for_docs(modified_shift["changes"]["added_docs"]))
    text = generate_message_text(changes)
    logging.info(f"Starting to send message to {len(users)} users.")

    for user in users:
        user_id = user["id"]
        try:
            await bot.send_message(
                user_id, text, parse_mode="HTML", disable_web_page_preview=True
            )
        except TelegramForbiddenError:
            logging.warning(f"User {user_id} has blocked the bot. Cannot send message.")
        except TelegramBadRequest as e:
            logging.error(f"Failed to send message to user {user_id}: {e}")
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while sending message to user {user_id}: {e}"
            )

    for spisok in new_spiski:
        await notify_about_spiski(bot, spisok)

    logging.info("Finished sending messages to all users.")
