import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
import os

CHANNEL_ID = os.environ['CHID']
ADMIN_IDS = [int(os.environ['ADID'])]

bot = Bot(token=os.environ['TOKEN'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

conn = sqlite3.connect('/data/posts.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        time TEXT NOT NULL
    )
''')
conn.commit()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@dp.message(F.text == "/start")
async def start_command(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Предложить идею")]],
        resize_keyboard=True
    )
    await message.reply(
        "Привет! Я бот для публикации постов в канале.\n"
        "Нажми на кнопку 'Предложить идею' или используй команду /post, чтобы предложить свой пост.",
        reply_markup=keyboard
    )

@dp.message(F.text == "Предложить идею")
async def suggest_idea(message: Message):
    await message.reply(
        "Пожалуйста, напиши свой пост, начиная с команды /post.\n"
        "Например: /post Это мой пост для канала!"
    )

@dp.message(F.text.startswith("/post"))
async def handle_post(message: Message):
    user_id = message.from_user.id
    post_text = message.text[6:].strip()
    
    if not post_text:
        await message.reply("Пожалуйста, добавьте текст после команды /post")
        return

    if is_admin(user_id):
        cursor.execute('INSERT INTO posts (text, time) VALUES (?, ?)',
                      (post_text, datetime.now().strftime("%H:%M")))
        conn.commit()
        
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text
        )
        await message.reply("Пост опубликован!")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{message.message_id}_{user_id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{message.message_id}_{user_id}")
            ]
        ])
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                chat_id=admin_id,
                text=f"Новое предложение поста от {message.from_user.full_name}:\n\n{post_text}",
                reply_markup=keyboard
            )
        
        await message.reply("Ваш пост отправлен администраторам на проверку!")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав для одобрения постов")
        return

    data_parts = callback.data.split("_")
    message_id = data_parts[1]
    user_id = int(data_parts[2])
    suggested_text = callback.message.text.split("\n\n")[1]
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="Ваш пост одобрен! Администратор скоро его опубликует."
        )
    except Exception as e:
        print(f"Ошибка при отправке сообщения пользователю: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\nСтатус: Одобрен ✅\n\nДля публикации используйте команду:\n/post {suggested_text}"
    )

@dp.callback_query(F.data.startswith("reject_"))
async def reject_post(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав для отклонения постов")
        return

    data_parts = callback.data.split("_")
    message_id = data_parts[1]
    user_id = int(data_parts[2])
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text="Ваш пост был отклонен."
        )
    except Exception as e:
        print(f"Ошибка при отправке сообщения пользователю: {e}")
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\nСтатус: Отклонен ❌"
    )

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())