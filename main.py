import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# Берем ключи из настроек Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")

logging.basicConfig(level=logging.INFO)

# Подключаем мозг DeepSeek
client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# Инициализируем бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Системный промпт (наша команда)
SYSTEM_PROMPT = """Ты — крутое ИИ-агентство PincherLab. 
Твоя команда: Менеджер (ты), Креативный директор, Копирайтер, Арт-директор и Дизайнер.
Ты общаешься с Владельцем (клиентом). 
Твоя задача: задавать вопросы (бриф), если задача непонятна, и выдавать креативные решения (тексты, идеи). 
Общайся профессионально, но дружелюбно."""

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Я твое ИИ-агентство PincherLab. Напиши мне задачу, и мы начнем!")

@dp.message()
async def handle_message(message: types.Message):
    await message.answer("Команда думает...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ]
        )
        answer = response.choices[0].message.content
        await message.answer(answer)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)
