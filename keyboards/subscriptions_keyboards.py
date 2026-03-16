from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_db_connection


def get_subscription_keyboard(user_id: int, topic_names):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (user_id,))
    subscriptions = cursor.fetchone()

    builder = InlineKeyboardBuilder()

    if subscriptions:
        for topic, name in topic_names.items():
            status_icon = "✅" if subscriptions[topic] else "❌"
            builder.button(
                text=f"{status_icon} {name}", callback_data=f"toggle_subscription:{topic}"
            )

    builder.adjust(1)
    return builder.as_markup()
