import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Токены
YANDEX_DISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

BASE_FOLDER = "Фото оборудования"

def folder_exists(path):
    """Проверка существования папки на Яндекс.Диске"""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
    params = {"path": path}
    response = requests.get(url, headers=headers, params=params)
    return response.status_code == 200

def create_folder(path):
    """Создать папку на Яндекс.Диске, если её нет"""
    if folder_exists(path):
        return False  # Папка уже существует
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
    params = {"path": path}
    response = requests.put(url, headers=headers, params=params)
    return response.status_code == 201

def upload_file(path, file_bytes):
    """Загрузка файла на Яндекс.Диск"""
    url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    headers = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
    params = {"path": path, "overwrite": "true"}
    response = requests.get(url, headers=headers, params=params)
    upload_url = response.json().get("href")
    requests.put(upload_url, data=file_bytes)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка присланного фото"""
    message = update.message
    caption = message.caption  # Номер накладной
    if not caption:
        await message.reply_text("Укажите номер накладной в подписи к фото.")
        return

    folder_path = f"{BASE_FOLDER}/{caption}"
    is_new_folder = create_folder(folder_path)

    # Получаем фото
    photo_file = await message.photo[-1].get_file()
    file_bytes = await photo_file.download_as_bytearray()

    # Имя файла по дате и времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{folder_path}/{timestamp}.jpg"

    upload_file(file_name, file_bytes)

    if is_new_folder:
        await message.reply_text(f"Создана новая накладная и фото загружено в папку: {folder_path}")
    else:
        await message.reply_text(f"Фото добавлено в существующую накладную: {folder_path}")

def main():
    PORT = int(os.environ.get("PORT", "8443"))
    WEBHOOK_URL = "https://gidromag-bot.onrender.com"

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
