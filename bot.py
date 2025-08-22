import os
import logging
import requests
from io import BytesIO
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN")
YANDEX_API = "https://cloud-api.yandex.net/v1/disk/resources"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_PHOTOS = range(1)
user_photos = {}

def create_invoice_folder(invoice_number: str):
    """
    Создает подпапку с номером накладной внутри Фото оборудования
    """
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    base_folder = "/Фото оборудования"
    # создаем основную папку, если нет
    requests.put(YANDEX_API, params={"path": base_folder}, headers=headers)
    # создаем подпапку с номером накладной
    invoice_folder = f"{base_folder}/{invoice_number}"
    requests.put(YANDEX_API, params={"path": invoice_folder}, headers=headers)
    return invoice_folder

def upload_file_bytes(file_bytes, folder_path, filename):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    resp = requests.get(f"{YANDEX_API}/upload",
                        params={"path": f"{folder_path}/{filename}", "overwrite": "true"},
                        headers=headers)
    result = resp.json()
    if "href" not in result:
        print("Ошибка при получении URL для загрузки:", result)
        return False
    upload_url = result["href"]
    r = requests.put(upload_url, files={"file": file_bytes})
    if r.status_code == 201:
        print(f"{filename} успешно загружен")
        return True
    else:
        print("Ошибка загрузки:", r.text)
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_photos[update.effective_chat.id] = []
    await update.message.reply_text(
        "Привет! Отправь фото оборудования. Когда закончишь, напиши номер накладной."
    )
    return WAITING_PHOTOS

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    bio = BytesIO()
    await file.download(out=bio)
    bio.seek(0)
    user_photos.setdefault(update.effective_chat.id, []).append(bio)
    return WAITING_PHOTOS

async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    invoice_number = update.message.text.strip()
    photos = user_photos.pop(update.effective_chat.id, [])
    if not photos:
        await update.message.reply_text("Ошибка: фото не найдено. Сначала отправь фото.")
        return ConversationHandler.END
    folder_path = create_invoice_folder(invoice_number)
    for idx, bio in enumerate(photos, start=1):
        upload_file_bytes(bio, folder_path, f"{idx}.jpg")
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
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invoice),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)

    # Webhook для Render
    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_URL = f"https://gidromag-bot.onrender.com/{TELEGRAM_TOKEN}"  # <- поменяйте на свой URL

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
