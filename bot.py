import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import yadisk

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Токены берутся из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
YANDEX_DISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN")

# Подключение к Яндекс.Диску
y = yadisk.YaDisk(token=YANDEX_DISK_TOKEN)

# Основные папки
BASE_FOLDER = "Фото оборудования"

# Хранение состояния пользователя (номер накладной)
user_invoice = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли номер накладной:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in user_invoice:
        user_invoice[user_id] = text
        await update.message.reply_text(f"Накладная {text} сохранена. Пришли фото оборудования.")
    else:
        await update.message.reply_text("Я жду фото, пришли изображение.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_invoice:
        await update.message.reply_text("Сначала пришли номер накладной.")
        return

    invoice_number = user_invoice[user_id]
    photo_file = await update.message.photo[-1].get_file()
    file_path = f"{BASE_FOLDER}/{invoice_number}/{photo_file.file_id}.jpg"

    # Создаем папку на Яндекс.Диске, если нет
    folder_path = f"/{BASE_FOLDER}/{invoice_number}"
    try:
        if not y.exists(folder_path):
            y.mkdir(folder_path)
            logger.info(f"Создана папка на Яндекс.Диске: {folder_path}")
    except Exception as e:
        logger.error(f"Ошибка при создании папки {folder_path}: {e}")
        await update.message.reply_text(f"Ошибка при создании папки на Яндекс.Диске: {e}")
        return

    # Сохраняем фото во временный файл
    temp_path = f"/tmp/{photo_file.file_id}.jpg"
    await photo_file.download_to_drive(temp_path)

    # Загружаем на Яндекс.Диск
    try:
        y.upload(temp_path, f"/{file_path}", overwrite=True)
        logger.info(f"Файл загружен на Яндекс.Диск: /{file_path}")
        await update.message.reply_text(f"Фото сохранено в накладную {invoice_number}.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {file_path} на Яндекс.Диск: {e}")
        await update.message.reply_text(f"Ошибка при загрузке на Яндекс.Диск: {e}")
    finally:
        # Удаляем локальный файл
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"Локальный файл удален: {temp_path}")

async def reset_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_invoice:
        del user_invoice[user_id]
        await update.message.reply_text("Номер накладной сброшен. Пришли новый номер накладной.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_invoice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запуск webhook на Render
    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_URL = "https://gidromag-bot.onrender.com/"  # твой публичный URL
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
