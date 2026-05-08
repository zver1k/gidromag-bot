"""
Конфигурация для Telegram бота
"""

import os
from typing import List

# Токены (берутся из переменных окружения)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
YANDEX_DISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN")

# Основные настройки
BASE_FOLDER = "Фото оборудования"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://gidromag-bot.onrender.com/")
PORT = int(os.environ.get("PORT", 8443))

# Ограничения
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB для видео
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB для документов
MAX_PHOTOS_PER_INVOICE = 50
MAX_VIDEOS_PER_INVOICE = 10  # Максимум видео на накладную
MAX_DOCUMENTS_PER_INVOICE = 20  # Максимум документов на накладную

# Поддерживаемые форматы
SUPPORTED_PHOTO_FORMATS = ['.jpg', '.jpeg', '.png', '.jfif']
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.3g2', '.f4v', '.asf']
SUPPORTED_DOCUMENT_FORMATS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']

# Поведение бота
AUTO_EXIT_AFTER_PHOTO = False  # Автоматически выходить из накладной после загрузки фото
PHOTOS_FOR_AUTO_EXIT = 0  # Количество фото для автоматического выхода (0 = отключено)
SHOW_PHOTO_COUNT = True  # Показывать количество загруженных фото
INACTIVITY_TIMEOUT_SECONDS = 600  # 10 минут бездействия для автосброса накладной

# Валидация
INVOICE_MIN_LENGTH = 3
INVOICE_MAX_LENGTH = 50
INVOICE_PATTERN = r'^[а-яА-ЯёЁa-zA-Z0-9 _-]{3,50}$'

# Временные файлы
TEMP_DIR = "/tmp"
TEMP_FILE_CLEANUP_INTERVAL = 3600  # 1 час в секундах
TEMP_FILE_MAX_AGE = 3600  # 1 час в секундах

# Администраторы (замените на реальные ID)
ADMIN_IDS: List[int] = [
    177611260,  # Замените на реальные ID администраторов
]

# Логирование
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Сообщения об ошибках
ERROR_MESSAGES = {
    "quota_exceeded": "❌ Превышен лимит Яндекс.Диска\n\nОбратитесь к администратору для увеличения места.",
    "network_error": "❌ Проблема с сетью\n\nПопробуйте позже или проверьте интернет-соединение.",
    "access_denied": "❌ Нет доступа к Яндекс.Диску\n\nПроверьте токен и права доступа.",
    "file_too_large": "❌ Файл слишком большой!\n\nМаксимальный размер: {max_size}MB\nТекущий размер: {current_size}MB",
    "video_too_large": "❌ Видео слишком большое!\n\nМаксимальный размер: {max_size}MB\nТекущий размер: {current_size}MB",
    "unsupported_format": "❌ Неподдерживаемый формат файла!\n\nПоддерживаются фото: JPG, JPEG, PNG\nПоддерживаются видео: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, M4V, 3GP, 3G2, F4V, ASF",
    "unsupported_photo_format": "❌ Неподдерживаемый формат фото!\n\nПоддерживаются только: JPG, JPEG, PNG, JFIF",
    "unsupported_video_format": "❌ Неподдерживаемый формат видео!\n\nПоддерживаются только: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, M4V, 3GP, 3G2, F4V, ASF\nПоддерживается разрешение до 4K",
    "unsupported_document_format": "❌ Неподдерживаемый формат документа!\n\nПоддерживаются только: PDF, DOC, DOCX, XLS, XLSX",
    "invoice_limit_reached": "❌ Достигнут лимит файлов для накладной '{invoice}'\n\nМаксимум: {max_photos} фото и {max_videos} видео\nТекущее количество: {current_photos} фото, {current_videos} видео\n\nИспользуйте /reset для сброса и начала новой накладной.",
    "video_limit_reached": "❌ Достигнут лимит видео для накладной '{invoice}'\n\nМаксимум: {max_videos} видео\nТекущее количество: {current_videos}\n\nИспользуйте /reset для сброса и начала новой накладной.",
    "invoice_validation": "❌ {error}\n\nПопробуйте еще раз или используйте команду /reset для сброса.",
}

# Успешные сообщения
SUCCESS_MESSAGES = {
    "invoice_saved": "✅ Накладная '{invoice}' сохранена.\n\nТеперь пришлите фото, видео или документы оборудования.",
    "photo_saved": "✅ Фото успешно сохранено!\n\n📋 Накладная: {invoice}\n📁 Папка: {folder}\n📸 Файл: {filename}\n📏 Размер: {size}\n📊 Фото в накладной: {current}/{max}",
    "video_saved": "✅ Видео успешно сохранено!\n\n📋 Накладная: {invoice}\n📁 Папка: {folder}\n🎥 Файл: {filename}\n📏 Размер: {size}\n📊 Видео в накладной: {current}/{max}",
    "document_saved": "✅ Документ успешно сохранен!\n\n📋 Накладная: {invoice}\n📁 Папка: {folder}\n📄 Файл: {filename}\n📏 Размер: {size}\n📊 Документы в накладной: {current}/{max}",
    "invoice_reset": "🔄 Накладная '{invoice}' сброшена.\n📸 Было загружено фото: {photo_count}\n🎥 Было загружено видео: {video_count}\n📄 Было загружено документов: {document_count}\n\nПришлите новый номер накладной.",
    "folder_created": "✅ Создана папка на Яндекс.Диске: {path}",
    "temp_file_cleaned": "🗑️ Временный файл удален: {path}",
}

# Информационные сообщения
INFO_MESSAGES = {
    "waiting_photo": "📸 Я жду фото, видео или документы, пришлите файл.",
    "waiting_media": "📸 Я жду фото, видео или документы оборудования, пришлите файл.",
    "no_active_invoice": "ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.",
    "folder_exists": "📁 Папка уже существует: {path}",
    "write_test_warning": "⚠️ Предупреждение: возможны проблемы с правами записи в папку.",
    "approaching_limit": "⚠️ Внимание! Приближается лимит файлов для накладной '{invoice}'\nОсталось: {remaining_photos} фото, {remaining_videos} видео",
    "approaching_video_limit": "⚠️ Внимание! Приближается лимит видео для накладной '{invoice}'\nОсталось: {remaining} видео",
    "session_expired": "⏳ Прошло более 10 минут бездействия. Накладная сброшена.\n\nПришлите новый номер накладной.",
}

# Статистика
STATS_MESSAGES = {
    "bot_stats": "📊 **Статистика бота**\n\n⏱️ Время работы: {uptime}\n👥 Активных пользователей: {users}\n📋 Активных накладных: {invoices}\n📸 Всего загружено фото: {photos}\n🎥 Всего загружено видео: {videos}\n📸 Фото в накладных: {photos_in_invoices}\n🎥 Видео в накладных: {videos_in_invoices}\n📋 Всего накладных: {total_invoices}\n❌ Ошибок: {errors}\n\n🔄 Используйте /reset для сброса накладной\n🔍 Используйте /status для проверки сервисов",
    "bot_status": "🔍 **Статус бота**\n\n✅ **Telegram Bot**: Активен\n✅ **Яндекс.Диск**: Подключен\n📁 **Базовая папка**: {base_folder_status}\n\n💾 **Место на диске:**\n• Свободно: {free_space}\n• Всего: {total_space}\n• Использовано: {used_percent}%\n\n📊 **Статистика:**\n• Фото: {photos}\n• Видео: {videos}\n• Накладные: {invoices}\n• Ошибки: {errors}",
    "current_invoice": "📋 **Текущая накладная**\n\n🔢 Номер: {invoice}\n📸 Загружено фото: {photo_count}\n🎥 Загружено видео: {video_count}\n📸 Осталось фото: {remaining_photos}\n🎥 Осталось видео: {remaining_videos}\n📁 Папка: {folder}\n\n{status}",
}

# Справка
HELP_MESSAGE = """🤖 **Справка по командам**

📋 **Основные команды:**
• /start - Начать работу с новой накладной
• /reset - Сбросить текущую накладную
• /current - Показать текущую накладную
• /stats - Показать статистику бота
• /status - Показать статус бота и сервисов
• /help - Показать эту справку
• /userinfo - Информация о пользователе

👑 **Административные команды:**
• /adduser <ID> - Добавить пользователя в список разрешенных
• /removeuser <ID> - Удалить пользователя из списка разрешенных
• /listusers - Показать список всех разрешенных пользователей
• /cleanup - Очистка временных файлов

📋 **Как использовать:**
1. Отправьте /start
2. Введите номер накладной
3. Отправьте фото, видео или документы оборудования
4. Файлы автоматически сохранятся на Яндекс.Диск
5. Продолжайте загружать файлы или используйте /reset для завершения

⚠️ **Ограничения:**
• Максимальный размер фото: {max_photo_size}
• Максимальный размер видео: {max_video_size}
• Максимальный размер документов: 50MB
• Максимум фото на накладную: {max_photos}
• Максимум видео на накладную: {max_videos}
• Максимум документов на накладную: 20
• Поддерживаемые фото: JPG, JPEG, PNG, JFIF (конвертируется в JPG)
• Поддерживаемые видео: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, M4V, 3GP, 3G2, F4V, ASF (до 4K)
• Поддерживаемые документы: PDF, DOC, DOCX, XLS, XLSX

🔧 **Дополнительно:**
• Используйте /current для просмотра текущей накладной
• Используйте /status для проверки состояния сервисов
• Используйте /stats для просмотра статистики
• При ошибках используйте /reset для сброса

👥 **Управление пользователями:**
• Администраторы могут добавлять/удалять пользователей
• Используйте /adduser <ID> для добавления
• Используйте /removeuser <ID> для удаления
• Используйте /listusers для просмотра списка

💡 **Как узнать ID пользователя:**
Попросите пользователя отправить /start боту @userinfobot"""
