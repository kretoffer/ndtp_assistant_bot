from typing import Union

from aiogram.types import Message, CallbackQuery, InaccessibleMessage


def get_from_user_and_answer_from_update(update: Union[Message, CallbackQuery]):
    """
    -> (from_user, answer_funcrion)
    """
    from_user = None
    answer = None

    if isinstance(update, Message):
        from_user = update.from_user
        answer = update.answer
    elif isinstance(update, CallbackQuery):
        from_user = update.from_user
        if not update.message or isinstance(update.message, InaccessibleMessage):
            return (None, None)
        answer = update.message.edit_text

    return from_user, answer
