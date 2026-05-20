import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Messages:
    start_phrase: str = "👋 Привет! Я ндтп ассистент, могу сообщать о изменениях в списках, искать вас в списках, помочь написать проект и ответить на вопросы\n\n"\
                        "📆 Используйте /schedule чтобы посмотреть расписание\n"\
                        "📌 Используйте /subscriptions чтобы настроить оповещения\n"\
                        "👀 Используйте /districts чтобы узнать побольше о направлениях\n"\
                        "\n✏️ Чтобы поменять имя /edit_name"
    noname: str = "Если хочешь чтобы я искал тебя в списках и сообщал если найду, добавь свое имя через /edit_name"
    broadcast_start: str = "Начинаем рассылку. Отправьте сообщение, которое будет разослано всем пользователям."
    enter_name: str = "Введи свое имя и я буду сообщать тебе если увижу тебя в списках\nЕсли ты не хочешь вводить имя, то нажми отмена и тогда я тебе буду сообщать только о изменении календаря образовательных смен"
    enter_surname: str = "Теперь введи свою фамилию"
    action_canceled: str = "❌ Действие отменено"
    registration_successful: str = "🤓 Теперь буду тебя знать"
    error_occured: str = "🤓 Произошла ошибка, попробуй еще раз"
    subscriptions: str = "✅ - подписаны (вам будут приходить сообщения по этой теме)\n❌ - не подписаны (сообщения приходить не будут)\n\n<b>Ваши подписки на события:</b>"


@dataclass
class Config:
    token: str
    admin_id: int
    messages: Messages
    db_path: str = "data/database.db"
    old_data_path = "data/old_data.json"
    districts_data_path = "data/districts_data.json"
    dopusheni_data_path = "data/dopusheni_data.json"
    spiski_data_path = "data/spiski_data.json"
    districts_info_path = "data/districts_info.json"
    parsing_interval = 60
    districts_parsing_interval = 1800
    TOPIC_NAMES = {
        "new_removed_shifts": "Добавление/удаление смен",
        "dates": "Даты",
        "polozhenie": "Положение",
        "dopusheni": "Допущенные к тестам",
        "mesta_provedeniya": "Места проведения",
        "spiski": "Поступившие",
        #"directions": "Образовательные программы"
    }


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Haven't BOT_TOKEN in .env")
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        raise ValueError("Haven't ADMIN_ID in .env")
    return Config(
        token=token,
        admin_id=int(admin_id),
        messages=Messages(),
        db_path=os.getenv("DB_PATH", "data/database.db"),
    )
