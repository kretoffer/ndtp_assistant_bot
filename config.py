import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Config:
    token: str
    start_phrase: str = "Привет! Я ндтп ассистент, могу сообщать о изменениях в списках, искать вас в списках, помочь написать проект и ответить на вопросы"
    db_path: str = "data/database.db"

def load_config() -> Config:
    load_dotenv()
    return Config(
        token=os.getenv("BOT_TOKEN"),
        db_path=os.getenv("DB_PATH", "data/database.db")
    )
