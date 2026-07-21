import os
import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, InaccessibleMessage

from typing import Union

from tools import get_from_user_and_answer_from_update

from parser import get_districts_info
from database import check_username


districts_router = Router()


@districts_router.message(Command("districts"))
@districts_router.callback_query(lambda c: c.data == "districts")
async def districts(update: Union[Message, CallbackQuery]):
    from_user, answer = get_from_user_and_answer_from_update(update) # pyright: ignore[reportAssignmentType]
    if not from_user:
        return
    if isinstance(update, CallbackQuery):
        async def answer(text: str, reply_markup):
            if not update.message:
                return
            await update.message.answer(text=text, reply_markup=reply_markup)
            if not isinstance(update.message, InaccessibleMessage):
                await update.message.delete()

    check_username(from_user.id, from_user.username)
    text = "👀 Выберите направление о котором хотите узнать"

    directions = get_districts_info().keys() # pyright: ignore[reportOptionalMemberAccess]
    directions = sorted(directions)
    buttons = [InlineKeyboardButton(text=name, callback_data=f"direction_info:{id}") for id, name in enumerate(directions)]
    buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data="home"))
    markup = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])

    await answer(text, reply_markup=markup)


@districts_router.callback_query(F.data.startswith("direction_info:"))
async def direction_info(callback: CallbackQuery):
    if callback.data and callback.message:
        check_username(callback.from_user.id, callback.from_user.username)
        args = callback.data.split(":")

        direction_index = int(args[1])

        directions_info = get_districts_info()
        directions = sorted(directions_info.keys()) # type: ignore

        direction_name = directions[direction_index]
        direction = directions_info[direction_name] # pyright: ignore[reportOptionalSubscript]

        programs = direction["programs"]
        programs_names = sorted(programs.keys())

        back = ":".join(args[3:]) if len(args) > 3 else f"direction_info:{direction_index}"

        if len(args) == 2:
            buttons = [InlineKeyboardButton(text=name, callback_data=f"direction_info:{direction_index}:{id}") for id, name in enumerate(programs_names)]
            buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data="districts"))
            markup = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])

            text = f"<b>{direction_name}</b>"

            if direction["info"]:
                text += f"\n\n{direction['info']}"

            if callback.message and not isinstance(callback.message, InaccessibleMessage):
                await callback.message.delete()
            await answer_with_random_img(callback.message.answer, callback.message.answer_photo, direction_name, text, markup)

        elif len(args) >= 3:
            program_index = int(args[2])
            program_name = programs_names[program_index]
            program = programs[program_name]

            text = f"<b>{direction_name}\n\n{program_name}</b>\n\n{program}"

            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=back)]])

            await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
            if callback.message and not isinstance(callback.message, InaccessibleMessage):
                await callback.message.delete()

    await callback.answer()


async def answer_with_random_img(answer, answer_photo, direction_name, text, markup):
    image_dir_path = f"img/directions/{direction_name}"
    random_image_path = None
    if os.path.isdir(image_dir_path):
        image_files = [f for f in os.listdir(image_dir_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        if image_files:
            random_image_path = os.path.join(image_dir_path, random.choice(image_files))

    if random_image_path:
        photo = FSInputFile(random_image_path)
        await answer_photo(photo=photo, caption=text, reply_markup=markup, parse_mode="HTML")
    else:
        await answer(text=text, reply_markup=markup, parse_mode="HTML")
