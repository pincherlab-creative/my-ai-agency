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

# СИСТЕМНЫЙ ПРОМПТ (Правила агентства)
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

# Хранилище памяти для каждого пользователя (в оперативной памяти)
user_histories = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    # Очищаем память при старте
    user_histories[message.from_user.id] = []
    await message.answer(
        "👋 Привет! Я твое ИИ-агентство *PincherLab*.\n\n"
        "В моей команде: Менеджер, Креативный директор, Копирайтер, Арт-директор и Дизайнер.\n\n"
        "📝 *Как со мной работать:*\n"
        "— Просто напиши задачу, и я (как Менеджер) начну задавать вопросы (бриф).\n"
        "— Если нужен конкретный специалист, напиши: _«Копирайтер, придумай слоганы»_.\n"
        "— Чтобы начать новый проект с чистого листа, напиши /reset.\n\n"
        "Какая задача стоит перед нами сегодня?", 
        parse_mode="Markdown"
    )

@dp.message(Command("reset"))
async def reset(message: types.Message):
    # Очищаем историю диалога
    user_histories[message.from_user.id] = []
    await message.answer("🧹 Память очищена. Мы начинаем новый проект с чистого листа. Какая задача?")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    
    # Если пользователь новый, создаем ему память
    if user_id not in user_histories:
        user_histories[user_id] = []

    await message.answer("Команда думает...")

    try:
        # Собираем сообщения: системный промпт + история диалога + новое сообщение
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем последние 10 сообщений из истории (чтобы не перегружать запрос)
        for msg in user_histories[user_id][-10:]:
            messages.append(msg)
            
        # Добавляем текущее сообщение пользователя
        messages.append({"role": "user", "content": message.text})

        # Отправляем запрос в DeepSeek
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        
        answer = response.choices[0].message.content
        
        # Сохраняем в память вопрос и ответ
        user_histories[user_id].append({"role": "user", "content": message.text})
        user_histories[user_id].append({"role": "assistant", "content": answer})

        # Отправляем ответ
        await message.answer(answer)
        
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)
