from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from parser import get_old_data
from random import randint


def get_schedule_keyboard():
    shifts_data = get_old_data()
    keyboard_rows = []
    row = []
    for i, shift in enumerate(shifts_data):
        row.append(InlineKeyboardButton(text=f'{"📕📗📘📙"[randint(0, 3)]} {shift["name"]}', callback_data=f"shift-info:{i}"))
        if len(row) == 2:
            keyboard_rows.append(row)
            row = []
    if row:
        keyboard_rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_regions_keyboard(shift, keys: list):
    markup = []
    for i, region in enumerate(keys):
        if region == "Информационные и компьютерные технологии":
            region = f"⚠️ {region} ⚠️"
        markup.append([InlineKeyboardButton(text=region, callback_data=f"spiski:{shift}:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=markup)
