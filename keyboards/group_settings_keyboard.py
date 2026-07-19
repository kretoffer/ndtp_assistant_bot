from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_group_settings


def get_group_settings_keyboard(group_id: int, settings: dict):
    row = get_group_settings(group_id)

    builder = InlineKeyboardBuilder()

    if row:
        for key, name in settings.items():
            try:
                status_icon = "✅" if row[key] else "❌"
            except (IndexError, KeyError):
                continue
            builder.button(
                text=f"{status_icon} {name}",
                callback_data=f"toggle_group_setting:{key}",
            )

    builder.adjust(1)
    return builder.as_markup()
