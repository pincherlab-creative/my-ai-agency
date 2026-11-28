import os
import logging
import tempfile
import random
import asyncio
import urllib.parse
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from openai import OpenAI
from pypdf import PdfReader
import docx

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")

ADMIN_ID = 7172384171 
DATA_DIR = "/data"

logging.basicConfig(level=logging.INFO)

client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
audio_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ОБНОВЛЕННЫЙ СИСТЕМНЫЙ ПРОМПТ
SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. 
Твоя команда состоит из профессионалов с именами:
- Менеджер: Даша (Ведет проект, общается с клиентом, задает вопросы по брифу).
- Креативный директор: Саша (Ищет большие идеи, инсайты).
- Копирайтер: Паша (Пишет тексты, слоганы, нейминг).
- Арт-директор: Наташа (Отвечает за визуальный стиль, референсы).
- Дизайнер: Глаша (Описывает макеты).
- SMM-менеджер, Таргетолог, Стратег (подключаются по запросу).

ПРАВИЛО РОЛЕЙ: Внимательно смотри на то, как к тебе обращается Владелец. Если он пишет "Саша, придумай...", "Паша, напиши...", "Даша, задай вопросы...", ты должен отвечать ИСКЛЮЧИТЕЛЬНО от лица этого специалиста (используя его экспертизу). Если Владелец просто ставит задачу, отвечай как Даша (Менеджер) и веди бриф.

Твоя задача: решать бизнес-задачи клиента, а не просто угождать. Отвечай профессионально, но живо."""

active_client = {}

TOPICS = [
    "Современные тренды в диджитал-рекламе 2024-2025",
    "Как работают лучшие рекламные кампании на фестивале Каннские Львы",
    "Психология потребителя: почему люди покупают",
    "Нейминг: как создавать бренды, которые запоминаются",
    "Визуальные тренды в дизайне: минимализм против максимализма"
]

def get_client_file(client_name):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    return os.path.join(DATA_DIR, f"{client_name}.json")

def save_history(client_name, history):
    with open(get_client_file(client_name), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_history(client_name):
    file_path = get_client_file(client_name)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def get_knowledge_base():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "База знаний пока пуста."

def create_word_document(text: str) -> str:
    doc = docx.Document()
    for paragraph in text.split('\n'):
        if paragraph.strip():
            doc.add_paragraph(paragraph)
    file_path = "report.docx"
    doc.save(file_path)
    return file_path

async def daily_report_scheduler():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0:
            await send_daily_report(ADMIN_ID)
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(30)

async def send_daily_report(chat_id: int):
    topic = random.choice(TOPICS)
    prompt = f"Ты — Саша (Креативный директор). Проведи исследование на тему: '{topic}'. Напиши краткий отчет (до 1000 символов). Выдели 3 главных инсайта."
    try:
        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
        report = response.choices[0].message.content
        text = f"☀️ *Утренний отчет PincherLab*\n\n*Тема:* {topic}\n\n{report}"
        max_length = 4000
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            await bot.send_message(chat_id, chunk, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка отчета: {e}")

@dp.message(Command("clients"))
async def list_clients(message: types.Message):
    if not os.path.exists(DATA_DIR):
        await message.answer("Пока нет ни одного клиента.")
        return
    files = [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    if not files:
        await message.answer("Пока нет ни одного клиента.")
    else:
        client_list = "\n".join([f"• {f}" for f in files])
        await message.answer(f"📁 *Твои клиенты:*\n{client_list}", parse_mode="Markdown")

@dp.message(Command("new_client"))
async def new_client(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Напиши имя клиента: /new_client Кофейня")
        return
    client_name = parts[1].strip()
    active_client[message.from_user.id] = client_name
    save_history(client_name, [])
    await message.answer(f"✅ Клиент *{client_name}* создан и выбран. Даша (Менеджер) готова к работе!", parse_mode="Markdown")

@dp.message(Command("switch"))
async def switch_client(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Напиши имя клиента: /switch Кофейня")
        return
    client_name = parts[1].strip()
    if os.path.exists(get_client_file(client_name)):
        active_client[message.from_user.id] = client_name
        await message.answer(f"🔄 Переключился на клиента *{client_name}*.", parse_mode="Markdown")
    else:
        await message.answer(f"Клиент *{client_name}* не найден. Создай его через /new_client", parse_mode="Markdown")

@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Твой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message(Command("report"))
async def manual_report(message: types.Message):
    await message.answer("🧠 Саша (Креативный директор) изучает новые тренды...")
    await send_daily_report(message.from_user.id)

@dp.message(Command("word"))
async def get_word_report(message: types.Message):
    await message.answer("📝 Готовлю документ Word...")
    user_id = message.from_user.id
    client_name = active_client.get(user_id)
    if not client_name:
        await message.answer("Сначала выбери или создай клиента (/new_client или /switch).")
        return
    
    history = load_history(client_name)
    if len(history) > 1:
        last_answer = history[-1]["content"]
        file_path = create_word_document(last_answer)
        document = FSInputFile(file_path, filename=f"{client_name}_Report.docx")
        await message.answer_document(document, caption=f"Документ для клиента {client_name} готов!")
        os.remove(file_path)
    else:
        await message.answer("По этому клиенту пока нет ответов.")

@dp.message(Command("start"))
async def start(message: types.Message):
    active_client[message.from_user.id] = None
    await message.answer(
        "👋 Привет! Я твое ИИ-агентство *PincherLab*.\n\n"
        "Наша команда: Даша, Саша, Паша, Наташа, Глаша и другие.\n\n"
        "Для работы создай клиента: `/new_client Имя`\n"
        "Посмотреть всех: `/clients`\n"
        "Переключиться: `/switch Имя`\n\n"
        "А потом просто пиши задачи или отправляй голосовые!",
        parse_mode="Markdown"
    )

@dp.message(Command("reset"))
async def reset(message: types.Message):
    client_name = active_client.get(message.from_user.id)
    if client_name:
        save_history(client_name, [])
        await message.answer(f"🧹 Память клиента *{client_name}* очищена.", parse_mode="Markdown")
    else:
        await message.answer("🧹 Память очищена. Начинаем новый проект. Какая задача?")

@dp.message(lambda message: message.document and message.document.mime_type == "application/pdf")
async def handle_pdf(message: types.Message):
    user_id = message.from_user.id
    client_name = active_client.get(user_id)
    if not client_name:
        await message.answer("Сначала выбери клиента (/new_client или /switch).")
        return
    
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
        await process_text(message, prompt, user_id, client_name)
    except Exception as e:
        await message.answer(f"Ошибка чтения PDF: {e}")

@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    client_name = active_client.get(user_id)
    if not client_name:
        await message.answer("Сначала выбери клиента (/new_client или /switch).")
        return
        
    await message.answer("🎤 Слушаю голосовое...")
    try:
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            await bot.download_file(file_path, temp_file.name)
            temp_file_name = temp_file.name
        with open(temp_file_name, "rb") as audio_file:
            transcript = audio_client.audio.transcriptions.create(model="whisper-large-v3", file=audio_file)
        os.remove(temp_file_name)
        text_from_voice = transcript.text
        await message.answer(f"📝 Я услышал: «{text_from_voice}»\n\nКоманда думает...")
        await process_text(message, text_from_voice, user_id, client_name)
    except Exception as e:
        await message.answer(f"Ошибка распознавания: {e}")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    client_name = active_client.get(user_id)
    if not client_name:
        await message.answer("Сначала выбери клиента (/new_client или /switch).")
        return
    
    text = message.text.lower()
    
    if "нарисуй" in text or "сгенерируй" in text or "визуал" in text:
        await message.answer("🎨 Наташа (Арт-директор) придумывает концепт...")
        prompt_for_ai = f"""
        Ты — арт-директор. Создай детальный промпт на английском языке для нейросети-художника. 
        Задача: нарисовать красивый визуал (фон, атмосферу, предметы) для рекламы. 
        ВАЖНО: НИКАКОГО ТЕКСТА, букв или надписей на картинке. Только визуальный образ.
        Запрос клиента: {message.text}
        Ответь ТОЛЬКО английским текстом промпта.
        """
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt_for_ai}]
            )
            english_prompt = response.choices[0].message.content.strip()
            encoded_prompt = urllib.parse.quote(english_prompt)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"
            
            await message.answer_photo(
                photo=image_url, 
                caption=f"Визуальный концепт от Наташи готов! 🎨\n\n_Промпт: {english_prompt}_", 
                parse_mode="Markdown"
            )
            
            history = load_history(client_name)
            history.append({"role": "user", "content": message.text})
            history.append({"role": "assistant", "content": f"[Сгенерирован визуал] {english_prompt}"})
            save_history(client_name, history)
            
        except Exception as e:
            await message.answer(f"Ошибка рисования: {e}")
    else:
        await message.answer("Даша (Менеджер) думает...")
        await process_text(message, message.text, user_id, client_name)

async def process_text(message: types.Message, text: str, user_id: int, client_name: str):
    try:
        knowledge = get_knowledge_base()
        full_system_prompt = f"{SYSTEM_PROMPT}\n\nВот наша база знаний:\n{knowledge}\n\nТы сейчас работаешь над проектом клиента: {client_name}"
        
        history = load_history(client_name)
        messages = [{"role": "system", "content": full_system_prompt}]
        
        for msg in history[-10:]:
            messages.append(msg)
            
        messages.append({"role": "user", "content": text})

        response = client.chat.completions.create(model="deepseek-chat", messages=messages)
        answer = response.choices[0].message.content
        
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": answer})
        save_history(client_name, history)

        max_length = 4000
        for i in range(0, len(answer), max_length):
            chunk = answer[i:i + max_length]
            await message.answer(chunk)
    except Exception as e:
        await message.answer(f"Ошибка мозга: {e}")

async def main():
    asyncio.create_task(daily_report_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
