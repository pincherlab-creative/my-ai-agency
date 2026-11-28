import os
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI
from pypdf import PdfReader  # <--- Новая библиотека для PDF

# Берем ключи из настроек Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY") 

logging.basicConfig(level=logging.INFO)

client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
audio_client = OpenAI(api_key=OPENAI_KEY)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. 
Твоя команда: Менеджер (ты), Креативный директор, Копирайтер, Арт-директор и Дизайнер.
Ты общаешься с Владельцем. Твоя задача: задавать вопросы (бриф) и выдавать креативные решения.
Отвечай профессионально, но живо."""

user_histories = {}

def get_knowledge_base():
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "База знаний пока пуста."

@dp.message(Command("start"))
async def start(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer(
        "👋 Привет! Я твое ИИ-агентство *PincherLab*.\n\n"
        "Теперь я умею читать *PDF-файлы*! 📄\n"
        "Отправь мне бриф или презентацию, и я их изучу.\n\n"
        "— Можно писать текст или отправлять голосовые.\n"
        "— Для нового проекта: /reset.",
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
    
    await message.answer("📄 Читаю PDF-файл, это может занять пару секунд...")
    
    try:
        # Скачиваем файл
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            await bot.download_file(file_path, temp_file.name)
            temp_file_name = temp_file.name

        # Читаем текст из PDF
        reader = PdfReader(temp_file_name)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
        
        os.remove(temp_file_name)
        
        if not text_content.strip():
            await message.answer("В этом PDF нет текста (возможно, это картинки). Я не могу его прочитать.")
            return

        # Отправляем текст в DeepSeek
        prompt = f"Я отправил тебе PDF-файл. Вот его содержимое:\n\n{text_content[:8000]}\n\nПроанализируй этот документ и задай вопросы для брифа или выдай идеи."
        await process_text(message, prompt, user_id)

    except Exception as e:
        await message.answer(f"Ошибка чтения PDF: {e}")

# ОБРАБОТЧИК ГОЛОСОВЫХ
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
                model="whisper-1", 
                file=audio_file
            )
        
        os.remove(temp_file_name)
        text_from_voice = transcript.text
        
        await message.answer(f"📝 Я услышал: «{text_from_voice}»\n\nКоманда думает...")
        await process_text(message, text_from_voice, user_id)

    except Exception as e:
        await message.answer(f"Ошибка распознавания: {e}")

# ОБРАБОТЧИК ТЕКСТА
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    await message.answer("Команда думает...")
    await process_text(message, message.text, user_id)

# ОБЩАЯ ФУНКЦИЯ
async def process_text(message: types.Message, text: str, user_id: int):
    try:
        knowledge = get_knowledge_base()
        full_system_prompt = f"{SYSTEM_PROMPT}\n\nВот наша база знаний и правила:\n{knowledge}"
        
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

        await message.answer(answer)
        
    except Exception as e:
        await message.answer(f"Ошибка мозга: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)
