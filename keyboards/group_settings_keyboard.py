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
                callback_data=f"gs_toggle:{group_id}:{key}",
            )

        try:
            current_shift = row["selected_shift"]
        except (IndexError, KeyError):
            current_shift = None
        shift_label = current_shift if current_shift else "Все смены"
        builder.button(
            text=f"🎯 {shift_label}",
            callback_data=f"gs_select_shift:{group_id}",
        )

    builder.adjust(1)
    return builder.as_markup()


def get_shift_selection_keyboard(shifts: list, current_shift: str | None, group_id: int):
    builder = InlineKeyboardBuilder()

    all_icon = "✅" if current_shift is None else "📋"
    builder.button(text=f"{all_icon} Все смены", callback_data=f"gs_set_all:{group_id}")

    for i, shift in enumerate(shifts):
        icon = "✅" if shift["name"] == current_shift else "📋"
        builder.button(
            text=f"{icon} {shift['name']}",
            callback_data=f"gs_set_idx:{group_id}:{i}",
        )

    builder.button(text="🔙 Назад", callback_data=f"gs_back:{group_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_group_selection_keyboard(groups: list[tuple[int, str]]):
    builder = InlineKeyboardBuilder()
    for group_id, title in groups:
        builder.button(text=title, callback_data=f"gs_select_group:{group_id}")
    builder.adjust(1)
    return builder.as_markup()
