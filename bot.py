import asyncio
import logging
import os
import signal
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from config import TELEGRAM_TOKEN, YANDEX_DISK_TOKEN, BASE_FOLDER, PORT, WEBHOOK_URL
import database as db
from services import session_service, users_service, yadisk_service, stats_service
from handlers import commands, media, admin

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN обязателен для работы бота")
if not YANDEX_DISK_TOKEN:
    raise ValueError("YANDEX_DISK_TOKEN обязателен для работы бота")


async def _post_shutdown(application) -> None:
    """Save stats to Yandex.Disk before shutdown."""
    logger.info("📴 Завершение работы, сохраняем статистику...")
    await stats_service.save_to_remote()


async def _post_init(application) -> None:
    """Runs after the Application starts but before polling/webhook begins."""
    await db.init_db()
    logger.info("✅ База данных инициализирована")

    await yadisk_service.ensure_folder(f"/{BASE_FOLDER}")
    logger.info(f"✅ Базовая папка на Яндекс.Диске: /{BASE_FOLDER}")

    await users_service.load()
    logger.info(f"👥 Пользователей загружено: {len(users_service.ALLOWED_USERS)}")

    await session_service.load_from_db()

    await stats_service.load_from_remote()
    logger.info("📊 Статистика загружена с Яндекс.Диска")

    asyncio.ensure_future(session_service.start_cleanup_task())
    asyncio.ensure_future(stats_service.start_periodic_save_task())
    logger.info("🧹 Фоновые задачи запущены (очистка сессий + сохранение статистики)")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ Ошибка при обработке обновления: {context.error}")
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте ещё раз или обратитесь к администратору."
            )
        except Exception:
            pass


def main():
    logger.info("🚀 Запуск Telegram бота...")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_error_handler(error_handler)

    # Commands
    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("reset", commands.reset_invoice))
    app.add_handler(CommandHandler("cancel", commands.reset_invoice))
    app.add_handler(CommandHandler("current", commands.current_invoice))
    app.add_handler(CommandHandler("stats", commands.stats))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("menu", commands.show_menu))
    app.add_handler(CommandHandler("userinfo", commands.user_info))

    # Admin
    app.add_handler(CommandHandler("adduser", admin.add_user))
    app.add_handler(CommandHandler("removeuser", admin.remove_user))
    app.add_handler(CommandHandler("listusers", admin.list_users))
    app.add_handler(CommandHandler("cleanup", admin.cleanup))

    # Callbacks
    app.add_handler(CallbackQueryHandler(commands.handle_callback, pattern="^menu_"))

    # Media & text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, commands.handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, media.handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, media.handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, media.handle_document))

    logger.info("✅ Все обработчики зарегистрированы")
    logger.info(f"🌐 Запуск webhook на порту {PORT}")
    logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}")

    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)


if __name__ == "__main__":
    main()
