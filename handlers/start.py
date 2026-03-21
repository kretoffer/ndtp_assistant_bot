from aiogram import Router
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import get_db_connection, check_username
from keyboards import cancel_keyboard


class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()


start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, config: Config, state: FSMContext):
    if not message.from_user:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?)", (message.from_user.id, message.from_user.username)
        )
        cursor.execute(
            "INSERT OR IGNORE INTO subscriptions (id, polozhenie, dopusheni, mesta_provedeniya, spiski, new_removed_shifts, dates) VALUES (?, 1, 1, 1, 1, 1, 1)", (message.from_user.id,)
        )
    conn.commit()

    if user and user[1] and user[2]:
        await message.answer(config.messages.start_phrase.replace("Привет!", f"Привет, {user[2]} {user[1]}!"))
    else:
        await state.set_state(Registration.waiting_for_name)
        await message.answer(
            config.messages.start_phrase + "\n\n" + config.messages.enter_name,
            reply_markup=cancel_keyboard,
        )


@start_router.message(Command("edit_name"))
async def cmd_edit_name(message: Message, config: Config, state: FSMContext):
    if not message.from_user:
        return
    check_username(message.from_user.id, message.from_user.username)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, username) VALUES (?)", (message.from_user.id, message.from_user.username)
    )
    conn.commit()

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

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET name = ?, surname = ? WHERE id = ?",
            (name, surname, message.from_user.id),
        )
        conn.commit()
        await message.answer(f"{config.messages.registration_successful}, {surname} {name}\n\nЧтобы поменять имя /edit_name")
    except Exception as e:
        await message.answer(config.messages.error_occured)
        print(e)
    finally:
        await state.clear()
