import os
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# Берем ключи из настроек Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY") 

logging.basicConfig(level=logging.INFO)

# Подключаем мозг DeepSeek (для текста)
client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# Подключаем уши OpenAI Whisper (для голоса)
audio_client = OpenAI(api_key=OPENAI_KEY)

# Инициализируем бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Базовый промпт
SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. 
Твоя команда: Менеджер (ты), Креативный директор, Копирайтер, Арт-директор и Дизайнер.
Ты общаешься с Владельцем. Твоя задача: задавать вопросы (бриф) и выдавать креативные решения.
Отвечай профессионально, но живо."""

user_histories = {}

# ФУНКЦИЯ ЧТЕНИЯ БАЗЫ ЗНАНИЙ
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

# ОБРАБОТЧИК ГОЛОСОВЫХ
@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
        
    await message.answer("🎤 Слушаю голосовое, перевожу в текст...")
    
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
        
        await message.answer(f"📝 Я услышал: «{text_from_voice}»\n\nКоманда думает над ответом...")
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

# ОБЩАЯ ФУНКЦИЯ С ЗАГРУЗКОЙ БАЗЫ ЗНАНИЙ
async def process_text(message: types.Message, text: str, user_id: int):
    try:
        # Читаем файл knowledge.txt
        knowledge = get_knowledge_base()
        
        # Формируем запрос, склеивая промпт и базу знаний
        full_system_prompt = f"{SYSTEM_PROMPT}\n\nВот наша база знаний и правила, которые ты ОБЯЗАН учитывать:\n{knowledge}"
        
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
