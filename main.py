import os
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# Берем ключи из настроек Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY") # <--- Новый ключ для распознавания голоса

logging.basicConfig(level=logging.INFO)

# Подключаем мозг DeepSeek (для текста)
client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# Подключаем уши OpenAI Whisper (для голоса)
audio_client = OpenAI(api_key=OPENAI_KEY)

# Инициализируем бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. Твоя команда состоит из виртуальных сотрудников. Ты общаешься с Владельцем.

ТВОЯ СТРУКТУРА:
1. Менеджер (Ты): Руководишь процессом, ведешь переговоры, задаешь вопросы (бриф), пишешь письма и финально передаешь результат.
2. Креативный кластер:
   - Креативный директор (ищет большие идеи, инсайты).
   - Копирайтер (пишет слоганы, тексты, нейминг).
   - Арт-директор (отвечает за визуальный стиль, референсы).
   - Дизайнер (описывает, как будет выглядеть макет).

ПРАВИЛА:
1. Если Владелец пишет "Копирайтер: [задача]", отвечай только от лица Копирайтера.
2. Если Владелец пишет "Креативный директор: [задача]", отвечай только от лица Креативного директора.
3. Если Владелец пишет просто задачу, отвечай как Менеджер: задавай вопросы для брифа (цели, аудитория, бюджет), пока картина не станет ясной.
4. Бриф заканчивается, когда ты понимаешь, что информации достаточно, ИЛИ когда Владелец говорит "Бриф окончен".
5. Стиль общения: Профессиональный, но живой.
"""

user_histories = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer(
        "👋 Привет! Я твое ИИ-агентство *PincherLab*.\n\n"
        "Теперь я умею понимать не только текст, но и *голосовые сообщения*! 🎤\n\n"
        "— Напиши задачу или отправь голосовое, и я (как Менеджер) начну бриф.\n"
        "— Если нужен специалист, напиши: _«Копирайтер, придумай слоганы»_.\n"
        "— Для нового проекта: /reset.\n\n"
        "Какая задача стоит перед нами сегодня?", 
        parse_mode="Markdown"
    )

@dp.message(Command("reset"))
async def reset(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer("🧹 Память очищена. Начинаем новый проект с чистого листа. Какая задача?")

# НОВЫЙ ОБРАБОТЧИК ДЛЯ ГОЛОСОВЫХ
@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
        
    await message.answer("🎤 Слушаю голосовое, перевожу в текст...")
    
    try:
        # Скачиваем файл из телеграма
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            await bot.download_file(file_path, temp_file.name)
            temp_file_name = temp_file.name

        # Отправляем в OpenAI Whisper
        with open(temp_file_name, "rb") as audio_file:
            transcript = audio_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        os.remove(temp_file_name)
        text_from_voice = transcript.text
        
        await message.answer(f"📝 Я услышал: «{text_from_voice}»\n\nКоманда думает над ответом...")
        
        # Дальше логика как с обычным текстом
        await process_text(message, text_from_voice, user_id)

    except Exception as e:
        await message.answer(f"Ошибка распознавания: {e}")

# Обычный текст
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    await message.answer("Команда думает...")
    await process_text(message, message.text, user_id)

# Общая функция для запроса в DeepSeek
async def process_text(message: types.Message, text: str, user_id: int):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        for msg in user_histories[user_id][-10:]:
            messages.append(msg)
            
        messages.append({"role": "user", "content": text})

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        
        answer = response.choices[0].message.content
        
        user_histories[user_id].append({"role": "user", "content": text})
        user_histories[user_id].append({"role": "assistant", "content": answer})

        await message.answer(answer)
        
    except Exception as e:
        await message.answer(f"Ошибка мозга: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)
