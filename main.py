from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from decouple import config
import pywhatkit as kit
import time
import sqlite3

conn = sqlite3.connect("whatsapp_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS phone_numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT
)
""")
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Добавить номер"), KeyboardButton("Установить сообщение")],
        [KeyboardButton("Показать номера"), KeyboardButton("Показать сообщение")],
        [KeyboardButton("Удалить номер"), KeyboardButton("Редактировать сообщение")],
        [KeyboardButton("Запустить рассылку")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Я бот для WhatsApp рассылок.\nВыбери действие:", reply_markup=reply_markup)

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь номер телефона (в формате с кодом страны, без +):")
    context.user_data["state"] = "waiting_for_number"

async def set_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь текст сообщения:")
    context.user_data["state"] = "waiting_for_message"

async def show_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT number FROM phone_numbers")
    numbers = cursor.fetchall()
    if not numbers:
        await update.message.reply_text("Список номеров пуст.")
    else:
        await update.message.reply_text("Список номеров:\n" + "\n".join(number[0] for number in numbers))

async def show_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT message FROM messages ORDER BY id DESC LIMIT 1")
    message = cursor.fetchone()
    if not message:
        await update.message.reply_text("Сообщение ещё не установлено.")
    else:
        await update.message.reply_text(f"Текущее сообщение:\n{message[0]}")

async def send_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT number FROM phone_numbers")
    numbers = cursor.fetchall()
    cursor.execute("SELECT message FROM messages ORDER BY id DESC LIMIT 1")
    message = cursor.fetchone()

    if not numbers:
        await update.message.reply_text("Список номеров пуст. Добавь хотя бы один номер.")
        return
    if not message:
        await update.message.reply_text("Сообщение не установлено. Установи текст сообщения.")
        return

    message = message[0]
    await update.message.reply_text("Начинаю рассылку...")
    for number in numbers:
        try:
            kit.sendwhatmsg_instantly(f"+{number[0]}", message, wait_time=15, tab_close=True, close_time=2)
            time.sleep(5)
        except Exception as e:
            await update.message.reply_text(f"Ошибка отправки на {number[0]}: {e}")

    await update.message.reply_text("Рассылка завершена!")

async def delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь номер, который хочешь удалить:")
    context.user_data["state"] = "waiting_for_number_deletion"

async def edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь новое сообщение для замены:")
    context.user_data["state"] = "waiting_for_message_edit"

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if state == "waiting_for_number":
        try:
            cursor.execute("INSERT INTO phone_numbers (number) VALUES (?)", (update.message.text,))
            conn.commit()
            await update.message.reply_text(f"Номер {update.message.text} добавлен!")
        except sqlite3.IntegrityError:
            await update.message.reply_text(f"Номер {update.message.text} уже существует.")
        context.user_data["state"] = None
    elif state == "waiting_for_message":
        cursor.execute("INSERT INTO messages (message) VALUES (?)", (update.message.text,))
        conn.commit()
        await update.message.reply_text("Сообщение установлено!")
        context.user_data["state"] = None
    elif state == "waiting_for_number_deletion":
        cursor.execute("DELETE FROM phone_numbers WHERE number = ?", (update.message.text,))
        conn.commit()
        await update.message.reply_text(f"Номер {update.message.text} удалён!")
        context.user_data["state"] = None
    elif state == "waiting_for_message_edit":
        cursor.execute("INSERT INTO messages (message) VALUES (?)", (update.message.text,))
        conn.commit()
        await update.message.reply_text("Сообщение обновлено!")
        context.user_data["state"] = None
    else:
        await update.message.reply_text("Неизвестная команда. Используй меню для выбора действий.")

TOKEN = config('TOKEN')

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Text("Добавить номер"), add_number))
    application.add_handler(MessageHandler(filters.Text("Установить сообщение"), set_message))
    application.add_handler(MessageHandler(filters.Text("Показать номера"), show_numbers))
    application.add_handler(MessageHandler(filters.Text("Показать сообщение"), show_message))
    application.add_handler(MessageHandler(filters.Text("Удалить номер"), delete_number))
    application.add_handler(MessageHandler(filters.Text("Редактировать сообщение"), edit_message))
    application.add_handler(MessageHandler(filters.Text("Запустить рассылку"), send_messages))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()

if __name__ == "__main__":
    main()
