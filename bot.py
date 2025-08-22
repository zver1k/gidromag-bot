import logging
import os
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# === Настройки из переменных окружения ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN")
YANDEX_API = "https://cloud-api.yandex.net/v1/disk/resources"

# === Логи ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния
WAITING_PHOTOS, WAITING_INVOICE = range(2)
user_photos = {}

# === Работа с Яндекс.Диском ===
def create_folder(invoice_number: str):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    folder_path = f"/Фото оборудования/{invoice_number}"
    requests.put(YANDEX_API, params={"path": folder_path}, headers=headers)
    return folder_path

def upload_file(file_path: str, folder_path: str, filename: str):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    upload_url = requests.get(
        f"{YANDEX_API}/upload",
        params={"path": f"{folder_path}/{filename}", "overwrite": "true"},
        headers=headers,
    ).json()["href"]

    with open(file_path, "rb") as f:
        requests.put(upload_url, files={"file": f})

# === Telegram-бот ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_photos[update.effective_chat.id] = []
    await update.message.reply_text(
        "Привет! Отправь фото или альбом 📸. Когда закончишь – напиши номер накладной."
    )
    return WAITING_PHOTOS

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = f"{file.file_id}.jpg"
    await file.download_to_drive(file_path)
    user_photos.setdefault(update.effective_chat.id, []).append(file_path)
    return WAITING_PHOTOS

async def handle_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = f"{file.file_id}.jpg"
    await file.download_to_drive(file_path)
    user_photos.setdefault(update.effective_chat.id, []).append(file_path)
    return WAITING_PHOTOS

async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    invoice_number = update.message.text.strip()
    photos = user_photos.pop(update.effective_chat.id, [])

    if not photos:
        await update.message.reply_text("Ошибка: фото не найдено. Сначала отправь фото.")
        return ConversationHandler.END

    folder_path = create_folder(invoice_number)
    for idx, file_path in enumerate(photos, start=1):
        upload_file(file_path, folder_path, f"{invoice_number}_{idx}.jpg")

    await update.message.reply_text(
        f"Загружено {len(photos)} фото в папку '{invoice_number}' на Яндекс.Диске ✅"
    )
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_album),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invoice),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
