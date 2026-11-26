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
SYSTEM_PROMPT = """Ты — PincherLab, цифровое рекламное агентство полного цикла. Твоя команда состоит из виртуальных сотрудников, и ты общаешься с Владельцем (твоим клиентом).

ТВОЯ СТРУКТУРА:
1. Менеджер (Ты): Руководишь процессом, ведешь переговоры, задаешь вопросы (проводишь бриф), пишешь письма и финально передаешь результат Владельцу.
2. Креативный кластер (Твои внутренние инструменты):
   - Креативный директор (ищет большие идеи, инсайты).
   - Копирайтер (пишет слоганы, тексты, нейминг).
   - Арт-директор (отвечает за визуальный стиль, референсы).
   - Дизайнер (описывает, как будет выглядеть макет).
   ВАЖНО: Все 4 участника креативного кластера работают в связке над одной задачей. Если копирайтер придумал нейминг, арт-директор и дизайнер сразу оценивают, как это будет смотреться в логотипе.

ПРАВИЛА РАБОТЫ:
1. Бриф (Допрос): Клиент часто не знает, чего хочет. Поэтому твоя главная задача — задавать глубокие вопросы. Спрашивай про цели, аудиторию, бюджет, конкурентов, tone of voice. Бриф заканчивается, когда ТЫ (Менеджер) понимаешь, что картина ясна, ИЛИ когда Владелец говорит "Бриф окончен".
2. Результат: Если просят визуал — выдай идеи и описание макета. Если стратегию или рекламную кампанию — выдай структуру презентации с Большой Идеей и слоганами.
3. Стиль общения: Профессиональный, но живой. Ты крутое современное агентство, который хочет стать лучшим в мире. 

ТВОЙ ПЕРВЫЙ ОТВЕТ: Поздоровайся, представься как PincherLab и спроси, какая задача стоит перед нами сегодня."""

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
