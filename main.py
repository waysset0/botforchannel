# Импортируем необходимые библиотеки
import asyncio  # Для работы с асинхронным программированием
import sqlite3  # Для работы с базами данных SQLite
from datetime import datetime  # Для работы с датой и временем
from aiogram import Bot, Dispatcher, F  # Импортируем классы для работы с Telegram API
from aiogram.enums import ParseMode  # Для определения режима обработки текста
from aiogram.types import (  # Импортируем типы данных для работы с сообщениями и клавиатурами
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.client.default import DefaultBotProperties  # Для задания свойств бота
import os  # Для работы с переменными окружения

# Получаем идентификатор канала из переменной окружения
CHANNEL_ID = os.environ['CHID']
# Получаем идентификаторы администраторов из переменной окружения и сохраняем в список
ADMIN_IDS = [int(os.environ['ADID'])]

# Создаем экземпляр бота с токеном и устанавливаем режим обработки текста по умолчанию
bot = Bot(token=os.environ['TOKEN'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
# Создаем экземпляр диспетчера для обработки сообщений и событий
dp = Dispatcher()

# Устанавливаем соединение с базой данных SQLite
conn = sqlite3.connect('/data/posts.db')
# Создаем объект курсора для выполнения SQL-запросов
cursor = conn.cursor()

# Создаем таблицу для хранения постов, если она не существует
cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        time TEXT NOT NULL
    )
''')
# Сохраняем изменения в базе данных
conn.commit()

# Функция для проверки, является ли пользователь администратором
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS  # Возвращает True, если пользователь в списке администраторов

# Обработчик команды /start
@dp.message(F.text == "/start")
async def start_command(message: Message):
    # Создаем клавиатуру с одной кнопкой "Предложить идею"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Предложить идею")]],
        resize_keyboard=True  # Автоматически подстраивает размер клавиатуры
    )
    # Отправляем приветственное сообщение с инструкциями
    await message.reply(
        "Привет! Я бот для публикации постов в канале.\n"
        "Нажми на кнопку 'Предложить идею' или используй команду /post, чтобы предложить свой пост.",
        reply_markup=keyboard  # Прикрепляем клавиатуру к сообщению
    )

# Обработчик сообщения "Предложить идею"
@dp.message(F.text == "Предложить идею")
async def suggest_idea(message: Message):
    # Отправляем сообщение с инструкциями по предложению поста
    await message.reply(
        "Пожалуйста, напиши свой пост, начиная с команды /post.\n"
        "Например: /post Это мой пост для канала!"
    )

# Обработчик сообщений, начинающихся с /post
@dp.message(F.text.startswith("/post"))
async def handle_post(message: Message):
    user_id = message.from_user.id  # Получаем идентификатор пользователя
    post_text = message.text[6:].strip()  # Извлекаем текст поста, убирая команду /post

    if not post_text:  # Проверяем, не пустой ли текст поста
        await message.reply("Пожалуйста, добавьте текст после команды /post")  # Запрашиваем текст
        return  # Завершаем выполнение функции

    if is_admin(user_id):  # Проверяем, является ли пользователь администратором
        # Вставляем новый пост в таблицу posts с текстом и текущим временем
        cursor.execute('INSERT INTO posts (text, time) VALUES (?, ?)',
                       (post_text, datetime.now().strftime("%H:%M")))
        conn.commit()  # Сохраняем изменения в базе данных

        # Отправляем пост в указанный канал
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text
        )
        await message.reply("Пост опубликован!")  # Уведомляем пользователя об успешной публикации
    else:  # Если пользователь не является администратором
        # Создаем инлайн-клавиатуру с кнопками "Одобрить" и "Отклонить"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{message.message_id}_{user_id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{message.message_id}_{user_id}")
            ]
        ])
        
        for admin_id in ADMIN_IDS:  # Цикл по всем администраторам
            # Отправляем сообщение каждому администратору о новом предложении поста
            await bot.send_message(
                chat_id=admin_id,
                text=f"Новое предложение поста от {message.from_user.full_name}:\n\n{post_text}",
                reply_markup=keyboard  # Прикрепляем клавиатуру к сообщению
            )
        
        await message.reply("Ваш пост отправлен администраторам на проверку!")  # Уведомляем пользователя о статусе его поста

@dp.callback_query(F.data.startswith("approve_"))  # Обработчик для колбек-запросов, начинающихся с "approve_"
async def approve_post(callback: CallbackQuery):  # Асинхронная функция для обработки одобрения поста
    if not is_admin(callback.from_user.id):  # Проверяем, является ли пользователь администратором
        await callback.answer("У вас нет прав для одобрения постов")  # Если нет, отправляем ответ с сообщением
        return  # Завершаем выполнение функции

    data_parts = callback.data.split("_")  # Разделяем данные колбек-запроса на части
    message_id = data_parts[1]  # Извлекаем идентификатор сообщения из данных
    user_id = int(data_parts[2])  # Извлекаем идентификатор пользователя и преобразуем в целое число
    suggested_text = callback.message.text.split("\n\n")[1]  # Извлекаем текст предложения поста

    try:
        await bot.send_message(  # Пытаемся отправить сообщение пользователю о том, что пост одобрен
            chat_id=user_id,  # Указываем идентификатор пользователя
            text="Ваш пост одобрен! Администратор скоро его опубликует."  # Текст сообщения
        )
    except Exception as e:  # Обрабатываем возможные исключения при отправке сообщения
        print(f"Ошибка при отправке сообщения пользователю: {e}")  # Выводим ошибку в консоль

    await callback.message.edit_text(  # Редактируем текст сообщения колбек-запроса
        f"{callback.message.text}\n\nСтатус: Одобрен ✅\n\nДля публикации используйте команду:\n/post {suggested_text}"  # Добавляем статус и инструкцию для публикации
    )

@dp.callback_query(F.data.startswith("reject_"))  # Обработчик для колбек-запросов, начинающихся с "reject_"
async def reject_post(callback: CallbackQuery):  # Асинхронная функция для обработки отклонения поста
    if not is_admin(callback.from_user.id):  # Проверяем, является ли пользователь администратором
        await callback.answer("У вас нет прав для отклонения постов")  # Если нет, отправляем ответ с сообщением
        return  # Завершаем выполнение функции

    data_parts = callback.data.split("_")  # Разделяем данные колбек-запроса на части
    message_id = data_parts[1]  # Извлекаем идентификатор сообщения из данных
    user_id = int(data_parts[2])  # Извлекаем идентификатор пользователя и преобразуем в целое число
    
    try:
        await bot.send_message(  # Пытаемся отправить сообщение пользователю о том, что пост отклонен
            chat_id=user_id,  # Указываем идентификатор пользователя
            text="Ваш пост был отклонен."  # Текст сообщения
        )
    except Exception as e:  # Обрабатываем возможные исключения при отправке сообщения
        print(f"Ошибка при отправке сообщения пользователю: {e}")  # Выводим ошибку в консоль
    
    await callback.message.edit_text(  # Редактируем текст сообщения колбек-запроса
        f"{callback.message.text}\n\nСтатус: Отклонен ❌"  # Добавляем статус отклонения
    )

async def main():  # Основная асинхронная функция для запуска бота
    try:
        await dp.start_polling(bot)  # Запускаем опрос для получения обновлений от Telegram
    finally:
        await bot.session.close()  # Закрываем сессию бота после завершения работы
        conn.close()  # Закрываем соединение с базой данных

if __name__ == "__main__":  # Проверяем, является ли данный файл исполняемым модулем
    asyncio.run(main())  # Запускаем основную функцию в асинхронном режиме
