import logging
import os
import tempfile

from aiogram import Bot, Router, F
from aiogram.types import Message
from groq import Groq

from config import Config
from database import get_group_settings

logger = logging.getLogger(__name__)

voice_router = Router()


@voice_router.message(F.voice | F.video_note)
async def handle_voice_message(message: Message, bot: Bot, config: Config):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not config.groq_api_key:
        return

    row = get_group_settings(message.chat.id)
    if row is None or not row["voice_to_text"]:
        return

    voice = message.voice
    video_note = message.video_note
    if voice:
        file_id = voice.file_id
        suffix = ".ogg"
    elif video_note:
        file_id = video_note.file_id
        suffix = ".mp4"
    else:
        return

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        file = await bot.get_file(file_id)

        temp_path = None
        try:
            temp_path = tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
            await bot.download(file, destination=temp_path)

            client = Groq(api_key=config.groq_api_key)
            with open(temp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=(temp_path, f.read()),
                    model="whisper-large-v3",
                    temperature=0,
                )

            await message.reply(result.text.strip())

        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        await message.reply("Не удалось распознать голосовое сообщение.")
