from typing import Union

from aiogram import Router
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import add_user, check_username, get_user_by_id, update_user_name
from keyboards.cancel_keyboard import cancel_keyboard

from tools import get_from_user_and_answer_from_update


class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()


start_router = Router()


@start_router.message(Command("start"))
@start_router.callback_query(lambda c: c.data == "home")
async def cmd_start(update: Union[Message, CallbackQuery], config: Config, state: FSMContext):
    from_user, answer = get_from_user_and_answer_from_update(update)

    if not from_user or not answer:
        return

    add_user(from_user.id, from_user.username)
    user = get_user_by_id(from_user.id)

    if user and user["name"] and user["surname"]:
        await answer(config.messages.start_phrase.replace("Привет!", f"Привет, {user['surname']} {user['name']}!"))
    else:
        await answer(config.messages.start_phrase + "\n\n" + config.messages.noname)


@start_router.message(Command("edit_name"))
async def cmd_edit_name(message: Message, config: Config, state: FSMContext):
    if not message.from_user:
        return
    add_user(message.from_user.id, message.from_user.username)
    check_username(message.from_user.id, message.from_user.username)

    await state.set_state(Registration.waiting_for_name)
    await message.answer(config.messages.enter_name, reply_markup=cancel_keyboard)


@start_router.callback_query(lambda c: c.data == "cancel_registration")
async def cancel_handler(
    callback_query: CallbackQuery, state: FSMContext, config: Config
):
    await state.clear()
    if callback_query.message and not isinstance(
        callback_query.message, InaccessibleMessage
    ):
        await callback_query.message.edit_text(config.messages.action_canceled)



@start_router.message(Registration.waiting_for_name)
async def name_entered(message: Message, state: FSMContext, config: Config):
    await state.update_data(name=message.text)
    await state.set_state(Registration.waiting_for_surname)
    await message.answer(config.messages.enter_surname, reply_markup=cancel_keyboard)


@start_router.message(Registration.waiting_for_surname)
async def surname_entered(message: Message, state: FSMContext, config: Config):
    if not message.from_user:
        return
    check_username(message.from_user.id, message.from_user.username)
    user_data = await state.get_data()
    name = user_data.get("name")
    surname = message.text

    try:
        update_user_name(message.from_user.id, name, surname)
        await message.answer(f"{config.messages.registration_successful}, {surname} {name}\n\nЧтобы поменять имя /edit_name")
    except Exception as e:
        await message.answer(config.messages.error_occured)
        print(e)
    finally:
        await state.clear()
