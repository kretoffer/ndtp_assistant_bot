import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Messages:
    start_phrase: str = "Привет! Я ндтп ассистент, могу сообщать о изменениях в списках, искать вас в списках, помочь написать проект и ответить на вопросы"
    enter_name: str = "Введи свое имя и я буду сообщать тебе если увижу тебя в списках\nЕсли ты не хочешь вводить имя, то нажми отмена и тогда я тебе буду сообщать только о изменении календаря образовательных смен"
    enter_surname: str = "Теперь введи свою фамилию"
    action_canceled: str = "Действие отменено"
    registration_successful: str = "Теперь буду тебя знать"
    error_occured: str = "Произошла ошибка, попробуй еще раз"

@dataclass
class Config:
    token: str
    messages: Messages
    db_path: str = "data/database.db"
    old_data_path = "data/old_data.json"

def load_config() -> Config:
    load_dotenv()
    return Config(
        token=os.getenv("BOT_TOKEN"),
        messages=Messages(),
        db_path=os.getenv("DB_PATH", "data/database.db")
    )
