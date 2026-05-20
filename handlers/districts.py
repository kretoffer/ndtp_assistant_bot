from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from typing import Union

from tools import get_from_user_and_answer_from_update


districts_router = Router()


@districts_router.message(Command("districts"))
@districts_router.callback_query(lambda c: c.data == "districts")
def districts(update: Union[Message, CallbackQuery]):
    from_user, answer = get_from_user_and_answer_from_update(update)
    if not from_user or not answer:
        return
