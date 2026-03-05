from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import get_db_connection
from keyboards import cancel_keyboard


class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()


start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, config: Config, state: FSMContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()

    if user[1] and user[2]:
        await message.answer(config.messages.start_phrase)
    else:
        await state.set_state(Registration.waiting_for_name)
        await message.answer(
            config.messages.start_phrase + "\n\n" + config.messages.enter_name,
            reply_markup=cancel_keyboard
        )


@start_router.message(Command("edit_name"))
async def cmd_edit_name(message: Message, config: Config, state: FSMContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()

    await state.set_state(Registration.waiting_for_name)
    await message.answer(
        config.messages.enter_name,
        reply_markup=cancel_keyboard
    )


@start_router.callback_query(lambda c: c.data == "cancel_registration")
async def cancel_handler(callback_query: CallbackQuery, state: FSMContext, config: Config):
    await state.clear()
    await callback_query.message.edit_text(config.messages.action_canceled)


@start_router.message(Registration.waiting_for_name)
async def name_entered(message: Message, state: FSMContext, config: Config):
    await state.update_data(name=message.text)
    await state.set_state(Registration.waiting_for_surname)
    await message.answer(config.messages.enter_surname, reply_markup=cancel_keyboard)


@start_router.message(Registration.waiting_for_surname)
async def surname_entered(message: Message, state: FSMContext, config: Config):
    user_data = await state.get_data()
    name = user_data.get("name")
    surname = message.text

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET name = ?, surname = ? WHERE id = ?",
                       (name, surname, message.from_user.id))
        conn.commit()
        await message.answer(config.messages.registration_successful)
    except Exception as e:
        await message.answer(config.messages.error_occured)
        print(e)
    finally:
        await state.clear()
