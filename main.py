import os
import logging
import tempfile
import random
import asyncio
from datetime import datetime, time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI
from pypdf import PdfReader

# Берем ключи из настроек Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")

# ТВОЙ ID (чтобы бот знал, кому писать)
ADMIN_ID = 7172384171 

logging.basicConfig(level=logging.INFO)

# Мозг (DeepSeek)
client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
# Уши (Groq)
audio_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. 
Твоя команда: Менеджер (ты), Креативный директор, Копирайтер, Арт-директор и Дизайнер.
Ты общаешься с Владельцем. Твоя задача: задавать вопросы (бриф) и выдавать креативные решения.
Отвечай профессионально, но живо."""

user_histories = {}

# Темы для самообразования
TOPICS = [
    "Современные тренды в диджитал-рекламе 2024-2025",
    "Как работают лучшие рекламные кампании на фестивале Каннские Львы",
    "Психология потребителя: почему люди покупают",
    "Нейминг: как создавать бренды, которые запоминаются",
    "Визуальные тренды в дизайне: минимализм против максимализма"
]

def get_knowledge_base():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "База знаний пока пуста."

# КОМАНДА ДЛЯ ПОЛУЧЕНИЯ ID
@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Твой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

# КОМАНДА ДЛЯ УТРЕННЕГО ОТЧЕТА (РУЧНОЙ ЗАПУСК)
@dp.message(Command("report"))
async def manual_report(message: types.Message):
    await message.answer("🧠 Изучаю новые тренды и готовлю отчет...")
    await send_daily_report(message.from_user.id)

# ФУНКЦИЯ ОТПРАВКИ ОТЧЕТА
async def send_daily_report(chat_id: int):
    topic = random.choice(TOPICS)
    prompt = f"Ты — креативный директор агентства. Проведи исследование на тему: '{topic}'. Напиши краткий, но емкий отчет (до 1000 символов). Выдели 3 главных инсайта, которые мы можем применить в работе."
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        report = response.choices[0].message.content
        
        text = f"☀️ *Утренний отчет PincherLab*\n\n*Тема исследования:* {topic}\n\n{report}"
        
        # Разбиваем на части, если длинно
        max_length = 4000
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            await bot.send_message(chat_id, chunk, parse_mode="Markdown")
            
    except Exception as e:
        await bot.send_message(chat_id, f"Ошибка при создании отчета: {e}")

@dp.message(Command("start"))
async def start(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer(
        "👋 Привет! Я твое ИИ-агентство *PincherLab*.\n\n"
        "Я умею слушать голосовые, читать PDF и учиться новому.\n"
        "Напиши /report, чтобы я изучил новые тренды и выдал отчет!",
        parse_mode="Markdown"
    )

@dp.message(Command("reset"))
async def reset(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer("🧹 Память очищена. Начинаем новый проект. Какая задача?")

# ОБРАБОТЧИК PDF
@dp.message(lambda message: message.document and message.document.mime_type == "application/pdf")
async def handle_pdf(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    await message.answer("📄 Читаю PDF-файл...")
    
    try:
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            await bot.download_file(file_path, temp_file.name)
            temp_file_name = temp_file.name

        reader = PdfReader(temp_file_name)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
        
        os.remove(temp_file_name)
        
        if not text_content.strip():
            await message.answer("В этом PDF нет текста.")
            return

        prompt = f"Я отправил тебе PDF-файл. Вот его содержимое:\n\n{text_content[:8000]}\n\nПроанализируй и задай вопросы."
        await process_text(message, prompt, user_id)

    except Exception as e:
        await message.answer(f"Ошибка чтения PDF: {e}")

# ОБРАБОТЧИК ГОЛОСА
@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
        
    await message.answer("🎤 Слушаю голосовое...")
    
    try:
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            await bot.download_file(file_path, temp_file.name)
            temp_file_name = temp_file.name

        with open(temp_file_name, "rb") as audio_file:
            transcript = audio_client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=audio_file
            )
        
        os.remove(temp_file_name)
        text_from_voice = transcript.text
        
        await message.answer(f"📝 Я услышал: «{text_from_voice}»\n\nКоманда думает...")
        await process_text(message, text_from_voice, user_id)

    except Exception as e:
        await message.answer(f"Ошибка распознавания: {e}")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    await message.answer("Команда думает...")
    await process_text(message, message.text, user_id)

async def process_text(message: types.Message, text: str, user_id: int):
    try:
        knowledge = get_knowledge_base()
        full_system_prompt = f"{SYSTEM_PROMPT}\n\nВот наша база знаний:\n{knowledge}"
        
        messages = [{"role": "system", "content": full_system_prompt}]
        
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

        max_length = 4000
        for i in range(0, len(answer), max_length):
            chunk = answer[i:i + max_length]
            await message.answer(chunk)
        
    except Exception as e:
        await message.answer(f"Ошибка мозга: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)
