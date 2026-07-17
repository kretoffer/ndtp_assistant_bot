import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config, load_config
from database import get_all_users

logger = logging.getLogger(__name__)

config: Config = load_config()

broadcast_router = Router()

class BroadcastState(StatesGroup):
    waiting_for_broadcast_message = State()

@broadcast_router.message(F.text == "/broadcast")
async def broadcast_command(message: Message, state: FSMContext):
    if message.from_user.id == config.admin_id: # pyright: ignore[reportOptionalMemberAccess]
        await message.answer(config.messages.broadcast_start)
        await state.set_state(BroadcastState.waiting_for_broadcast_message)
    else:
        await message.answer("У вас нет прав для этой команды.")

@broadcast_router.message(BroadcastState.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    users = get_all_users()
    for user in users:
        try:
            await message.copy_to(user['id'])
        except Exception as e:
            logger.warning(f"Failed to send message to user {user['id']}: {e}")
    await message.answer("Рассылка завершена.")
    await state.clear()
