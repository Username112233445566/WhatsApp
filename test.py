from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from decouple import config
import sqlite3
import re
import time

# Настройка SQLite
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

# Настройка Selenium
options = Options()
options.add_argument("--user-data-dir=./whatsapp_session")  # Путь для сохранения сессии
options.add_argument("--profile-directory=Default")
driver_service = Service(executable_path="chromedriver")  # Укажите путь к драйверу

def start_whatsapp_session():
    driver = webdriver.Chrome(service=driver_service, options=options)
    driver.get("https://web.whatsapp.com")
    input("Сканируйте QR-код, затем нажмите Enter...")
    return driver

def send_whatsapp_messages(driver, numbers, message):
    for number in numbers:
        try:
            url = f"https://wa.me/{number}"
            driver.get(url)
            time.sleep(5)

            # Нажимаем кнопку "Продолжить чат"
            continue_button = driver.find_element(By.XPATH, "//a[contains(@href, 'action=chat')]")
            continue_button.click()
            time.sleep(5)

            # Вводим сообщение
            message_box = driver.find_element(By.XPATH, "//div[@title='Напишите сообщение']")
            message_box.send_keys(message)
            message_box.send_keys(Keys.RETURN)

            time.sleep(2)  # Небольшая пауза между сообщениями
        except Exception as e:
            print(f"Ошибка при отправке на номер {number}: {e}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Добавить номер"), KeyboardButton("Установить сообщение")],
        [KeyboardButton("Показать номера"), KeyboardButton("Показать сообщение")],
        [KeyboardButton("Удалить номер")],
        [KeyboardButton("Запустить рассылку")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Я бот для WhatsApp рассылок.\nВыбери действие:", reply_markup=reply_markup)

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь номер телефона в формате +996XXXXXXXXX:")
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

async def delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь номер, который хочешь удалить:")
    context.user_data["state"] = "waiting_for_number_deletion"

async def send_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT number FROM phone_numbers")
    numbers = [row[0] for row in cursor.fetchall()]
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

    driver = start_whatsapp_session()
    send_whatsapp_messages(driver, numbers, message)
    driver.quit()

    await update.message.reply_text("Рассылка завершена!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if state == "waiting_for_number":
        number = update.message.text
        if re.fullmatch(r"\+996\d{9}", number):
            try:
                cursor.execute("INSERT INTO phone_numbers (number) VALUES (?)", (number,))
                conn.commit()
                await update.message.reply_text(f"Номер {number} добавлен!")
            except sqlite3.IntegrityError:
                await update.message.reply_text(f"Номер {number} уже существует.")
        else:
            await update.message.reply_text("Номер не соответствует формату +996XXXXXXXXX. Попробуй ещё раз.")
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
    application.add_handler(MessageHandler(filters.Text("Запустить рассылку"), send_messages))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()

if __name__ == "__main__":
    main()
