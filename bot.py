import os
import logging
import re
import signal
import sys
from datetime import datetime
import uuid
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import yadisk

# Импортируем конфигурацию
from config import (
    TELEGRAM_TOKEN, YANDEX_DISK_TOKEN, BASE_FOLDER, WEBHOOK_URL, PORT,
    MAX_FILE_SIZE, MAX_PHOTOS_PER_INVOICE, INVOICE_PATTERN,
    ADMIN_IDS, ERROR_MESSAGES, SUCCESS_MESSAGES, INFO_MESSAGES
)

# Компилируем регулярное выражение для валидации накладных
INVOICE_PATTERN = re.compile(INVOICE_PATTERN)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Флаг для корректного завершения
shutdown_flag = False

# Список разрешенных пользователей (замените на реальные ID)
ALLOWED_USERS = [
    177611260,  # Замените на реальные ID пользователей
]

# Файл для хранения разрешенных пользователей
USERS_FILE = "allowed_users.txt"

def load_allowed_users() -> list:
    """Загружает список разрешенных пользователей из файла"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = [int(line.strip()) for line in f if line.strip().isdigit()]
            logger.info(f"✅ Загружено {len(users)} разрешенных пользователей")
            return users
        else:
            # Создаем файл с базовым списком
            save_allowed_users(ALLOWED_USERS)
            return ALLOWED_USERS.copy()
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пользователей: {e}")
        return ALLOWED_USERS.copy()

def save_allowed_users(users: list) -> bool:
    """Сохраняет список разрешенных пользователей в файл"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            for user_id in sorted(users):
                f.write(f"{user_id}\n")
        logger.info(f"✅ Сохранено {len(users)} разрешенных пользователей")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователей: {e}")
        return False

def add_user_access(user_id: int) -> bool:
    """Добавляет пользователя в список разрешенных"""
    global ALLOWED_USERS
    if user_id not in ALLOWED_USERS:
        ALLOWED_USERS.append(user_id)
        save_allowed_users(ALLOWED_USERS)
        logger.info(f"✅ Добавлен доступ для пользователя {user_id}")
        return True
    return False

def remove_user_access(user_id: int) -> bool:
    """Удаляет пользователя из списка разрешенных"""
    global ALLOWED_USERS
    if user_id in ALLOWED_USERS:
        ALLOWED_USERS.remove(user_id)
        save_allowed_users(ALLOWED_USERS)
        logger.info(f"✅ Удален доступ для пользователя {user_id}")
        return True
    return False

def is_user_allowed(user_id: int) -> bool:
    """Проверяет, имеет ли пользователь доступ к боту"""
    # Администраторы всегда имеют доступ
    return user_id in ALLOWED_USERS or user_id in ADMIN_IDS

def signal_handler(signum, _):
    """Обработчик сигналов для корректного завершения"""
    global shutdown_flag
    logger.info(f"📴 Получен сигнал {signum}, завершаем работу...")
    shutdown_flag = True
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Токены берутся из переменных окружения
# TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# YANDEX_DISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN")

# Проверяем наличие обязательных переменных окружения
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не найден в переменных окружения!")
    raise ValueError("TELEGRAM_TOKEN обязателен для работы бота")

if not YANDEX_DISK_TOKEN:
    logger.error("❌ YANDEX_DISK_TOKEN не найден в переменных окружения!")
    raise ValueError("YANDEX_DISK_TOKEN обязателен для работы бота")

logger.info("✅ Все необходимые токены найдены")

def get_disk_info_safe():
    """Безопасно получает информацию о диске"""
    try:
        disk_info = y.get_disk_info()
        
        # Пытаемся получить информацию разными способами
        if hasattr(disk_info, 'space') and hasattr(disk_info.space, 'free'):
            return {
                'free': disk_info.space.free,
                'total': disk_info.space.total,
                'available': True
            }
        elif hasattr(disk_info, 'free'):
            return {
                'free': disk_info.free,
                'total': disk_info.total,
                'available': True
            }
        elif hasattr(disk_info, 'available'):
            return {
                'free': disk_info.available,
                'total': disk_info.total if hasattr(disk_info, 'total') else 0,
                'available': True
            }
        else:
            logger.warning(f"⚠️ Неизвестная структура ответа API: {type(disk_info)}")
            return {
                'free': 0,
                'total': 0,
                'available': False
            }
    except Exception as e:
        logger.error(f"❌ Ошибка при получении информации о диске: {e}")
        return {
            'free': 0,
            'total': 0,
            'available': False
        }

# Подключение к Яндекс.Диску
try:
    y = yadisk.YaDisk(token=YANDEX_DISK_TOKEN)
    
    # Логируем версию библиотеки
    try:
        logger.info(f"📦 Версия библиотеки yadisk: {yadisk.__version__}")
    except AttributeError:
        logger.info("📦 Версия библиотеки yadisk: неизвестна")
    
    # Проверяем подключение
    disk_info = y.get_disk_info()
    
    # Отладочная информация
    logger.info(f"📊 Структура ответа API: {type(disk_info)}")
    logger.info(f"📊 Атрибуты объекта: {dir(disk_info)}")
    
    # Получаем информацию о свободном месте
    try:
        free_space = disk_info.space.free
        total_space = disk_info.space.total
        free_gb = free_space // (1024**3)
        logger.info(f"✅ Подключение к Яндекс.Диску установлено. Свободно: {free_gb}GB")
    except AttributeError as attr_error:
        # Если структура ответа отличается, логируем базовую информацию
        logger.warning(f"⚠️ Неожиданная структура ответа API: {attr_error}")
        logger.info(f"✅ Подключение к Яндекс.Диску установлено")
        logger.info(f"📊 Информация о диске: {disk_info}")
        
        # Пытаемся найти информацию о диске альтернативным способом
        try:
            if hasattr(disk_info, 'free'):
                free_gb = disk_info.free // (1024**3)
                logger.info(f"✅ Найдено свободное место: {free_gb}GB (альтернативный способ)")
            elif hasattr(disk_info, 'available'):
                free_gb = disk_info.available // (1024**3)
                logger.info(f"✅ Найдено доступное место: {free_gb}GB (альтернативный способ)")
        except Exception as alt_error:
            logger.warning(f"⚠️ Альтернативные способы получения информации не сработали: {alt_error}")
            
except Exception as e:
    logger.error(f"❌ Ошибка подключения к Яндекс.Диску: {e}")
    raise

# Основные папки
# BASE_FOLDER = "Фото оборудования"

# Проверяем и создаем базовую папку при запуске
try:
    base_folder_path = f"/{BASE_FOLDER}"
    if not y.exists(base_folder_path):
        y.mkdir(base_folder_path)
        logger.info(f"✅ Создана базовая папка: {base_folder_path}")
    else:
        logger.info(f"📁 Базовая папка уже существует: {base_folder_path}")
except Exception as e:
    logger.error(f"❌ Ошибка при создании базовой папки: {e}")
    raise

# Хранение состояния пользователя (номер накладной)
user_invoice = {}

# Хранение количества фото для каждой накладной
invoice_photo_count = {}

# Статистика использования
bot_stats = {
    "total_photos": 0,
    "total_invoices": 0,
    "errors": 0,
    "start_time": datetime.now()
}

# Константы для валидации
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
# MAX_PHOTOS_PER_INVOICE = 50
# INVOICE_PATTERN = re.compile(r'^[A-Za-z0-9\-_\.]{3,50}$')

def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в читаемом виде"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    else:
        return f"{size_bytes // (1024 * 1024)} MB"

def get_uptime() -> str:
    """Возвращает время работы бота"""
    uptime = datetime.now() - bot_stats["start_time"]
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}д {hours}ч {minutes}м"
    elif hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику бота"""
    uptime = get_uptime()
    active_users = len(user_invoice)
    
    # Подсчитываем общее количество уникальных накладных
    unique_invoices = len(set(user_invoice.values()))
    
    # Подсчитываем общее количество фото по всем накладным
    total_photos_in_invoices = sum(invoice_photo_count.values())
    
    stats_text = (
        f"📊 **Статистика бота**\n\n"
        f"⏱️ Время работы: {uptime}\n"
        f"👥 Активных пользователей: {active_users}\n"
        f"📋 Активных накладных: {unique_invoices}\n"
        f"📸 Всего загружено фото: {bot_stats['total_photos']}\n"
        f"📸 Фото в накладных: {total_photos_in_invoices}\n"
        f"📋 Всего накладных: {bot_stats['total_invoices']}\n"
        f"❌ Ошибок: {bot_stats['errors']}\n\n"
        f"🔄 Используйте /reset для сброса накладной\n"
        f"🔍 Используйте /status для проверки сервисов"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку по командам"""
    help_text = (
        f"🤖 **Справка по командам**\n\n"
        f"📋 **Основные команды:**\n"
        f"• /start - Начать работу с новой накладной\n"
        f"• /reset - Сбросить текущую накладную\n"
        f"• /current - Показать текущую накладную\n"
        f"• /stats - Показать статистику бота\n"
        f"• /status - Показать статус бота и сервисов\n"
        f"• /help - Показать эту справку\n"
        f"• /userinfo - Информация о пользователе\n\n"
        f"👑 **Административные команды:**\n"
        f"• /adduser <ID> - Добавить пользователя в список разрешенных\n"
        f"• /removeuser <ID> - Удалить пользователя из списка разрешенных\n"
        f"• /listusers - Показать список всех разрешенных пользователей\n"
        f"• /cleanup - Очистка временных файлов\n\n"
        f"📋 **Как использовать:**\n"
        f"1. Отправьте /start\n"
        f"2. Введите номер накладной\n"
        f"3. Отправьте фото оборудования\n"
        f"4. Фото автоматически сохранится на Яндекс.Диск\n"
        f"5. Продолжайте загружать фото или используйте /reset для завершения\n\n"
        f"⚠️ **Ограничения:**\n"
        f"• Максимальный размер файла: {format_file_size(MAX_FILE_SIZE)}\n"
        f"• Максимум фото на накладную: {MAX_PHOTOS_PER_INVOICE}\n"
        f"• Поддерживаемые форматы: JPG, JPEG, PNG\n\n"
        f"🔧 **Дополнительно:**\n"
        f"• Используйте /current для просмотра текущей накладной\n"
        f"• Используйте /status для проверки состояния сервисов\n"
        f"• Используйте /stats для просмотра статистики\n"
        f"• При ошибках используйте /reset для сброса\n\n"
        f"👥 **Управление пользователями:**\n"
        f"• Администраторы могут добавлять/удалять пользователей\n"
        f"• Используйте /adduser <ID> для добавления\n"
        f"• Используйте /removeuser <ID> для удаления\n"
        f"• Используйте /listusers для просмотра списка\n\n"
        f"💡 **Как узнать ID пользователя:**\n"
        f"Попросите пользователя отправить /start боту @userinfobot"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус бота и подключения к сервисам"""
    try:
        # Проверяем подключение к Яндекс.Диску
        disk_info = get_disk_info_safe()
        
        # Проверяем доступность базовой папки
        base_folder_exists = y.exists(f"/{BASE_FOLDER}")
        
        status_text = (
            f"🔍 **Статус бота**\n\n"
            f"✅ **Telegram Bot**: Активен\n"
            f"✅ **Яндекс.Диск**: Подключен\n"
            f"📁 **Базовая папка**: {'Существует' if base_folder_exists else 'Не найдена'}\n\n"
        )
        
        if disk_info['available']:
            free_space = format_file_size(disk_info['free'])
            total_space = format_file_size(disk_info['total'])
            used_percent = round((disk_info['total'] - disk_info['free']) / disk_info.total * 100, 1) if disk_info.total > 0 else 0
            
            status_text += (
                f"💾 **Место на диске:**\n"
                f"• Свободно: {free_space}\n"
                f"• Всего: {total_space}\n"
                f"• Использовано: {used_percent}%\n\n"
            )
        else:
            status_text += "💾 **Место на диске:** Информация недоступна\n\n"
        
        status_text += (
            f"📊 **Статистика:**\n"
            f"• Фото: {bot_stats['total_photos']}\n"
            f"• Накладные: {bot_stats['total_invoices']}\n"
            f"• Ошибки: {bot_stats['errors']}\n\n"
            f"⚙️ **Настройки:**\n"
            f"• Авто-выход: Отключен\n"
            f"• Фото для выхода: Не настроено"
        )
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except yadisk.exceptions.YaDiskError as e:
        error_msg = f"Ошибка при проверке статуса Яндекс.Диска: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")
    except Exception as e:
        error_msg = f"Ошибка при проверке статуса: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")

async def current_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о текущей накладной пользователя"""
    user_id = update.message.from_user.id
    
    if user_id not in user_invoice:
        await update.message.reply_text("ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.")
        return
    
    invoice_number = user_invoice[user_id]
    photo_count = invoice_photo_count.get(invoice_number, 0)
    remaining_photos = MAX_PHOTOS_PER_INVOICE - photo_count
    
    invoice_info = (
        f"📋 **Текущая накладная**\n\n"
        f"🔢 Номер: {invoice_number}\n"
        f"📸 Загружено фото: {photo_count}\n"
        f"📸 Осталось фото: {remaining_photos}\n"
        f"📁 Папка: {BASE_FOLDER}/{get_safe_folder_name(invoice_number)}\n\n"
    )
    
    if photo_count == 0:
        invoice_info += f"📸 Отправьте первое фото оборудования"
    elif remaining_photos <= 0:
        invoice_info += "❌ Достигнут лимит фото\nИспользуйте /reset для новой накладной"
    elif remaining_photos <= 5:
        invoice_info += f"⚠️ Осталось мало фото: {remaining_photos}"
    else:
        invoice_info += f"✅ Можно загрузить еще {remaining_photos} фото"
    
    await update.message.reply_text(invoice_info, parse_mode='Markdown')

def validate_invoice_number(invoice: str) -> tuple[bool, str]:
    """
    Валидация номера накладной
    Возвращает (is_valid, error_message)
    """
    try:
        if not invoice or not invoice.strip():
            return False, "Номер накладной не может быть пустым"
        
        invoice = invoice.strip()
        
        if len(invoice) < 3:
            return False, "Номер накладной должен содержать минимум 3 символа"
        
        if len(invoice) > 50:
            return False, "Номер накладной слишком длинный (максимум 50 символов)"
        
        # Проверяем, что INVOICE_PATTERN скомпилирован
        if not hasattr(INVOICE_PATTERN, 'match'):
            logger.error(f"❌ INVOICE_PATTERN не является скомпилированным регулярным выражением: {type(INVOICE_PATTERN)}")
            return False, "Ошибка валидации номера накладной"
        
        if not INVOICE_PATTERN.match(invoice):
            return False, "Номер накладной содержит недопустимые символы. Разрешены только буквы, цифры, дефис, подчеркивание и точка"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"❌ Ошибка при валидации номера накладной '{invoice}': {e}")
        return False, f"Ошибка валидации: {str(e)}"

def get_safe_folder_name(invoice: str) -> str:
    """
    Создает безопасное имя папки для Яндекс.Диска
    """
    # Заменяем недопустимые символы на подчеркивание
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', invoice)
    return safe_name

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Пришли номер накладной:\n\n"
        f"📸 Загружайте фото оборудования. Используйте /reset для завершения накладной."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    logger.info(f"📝 Получено сообщение от пользователя {user_id}: '{text}'")

    # Проверка доступа пользователя
    if not is_user_allowed(user_id):
        logger.warning(f"🚫 Пользователь {user_id} не имеет доступа к боту")
        await update.message.reply_text("❌ У вас нет прав для использования бота.")
        return

    # Валидация номера накладной
    logger.info(f"🔍 Валидация номера накладной: '{text}'")
    is_valid, error_message = validate_invoice_number(text)
    
    if not is_valid:
        logger.warning(f"❌ Некорректный номер накладной '{text}': {error_message}")
        await update.message.reply_text(f"❌ {error_message}\n\nПопробуйте еще раз или используйте команду /reset для сброса.")
        return

    if user_id not in user_invoice:
        user_invoice[user_id] = text
        invoice_photo_count[text] = 0
        bot_stats["total_invoices"] += 1
        logger.info(f"✅ Создана новая накладная '{text}' для пользователя {user_id}")
        await update.message.reply_text(f"✅ Накладная '{text}' сохранена.\n\nТеперь пришлите фото оборудования.")
    else:
        logger.info(f"📸 Пользователь {user_id} уже имеет активную накладную '{user_invoice[user_id]}'")
        await update.message.reply_text("📸 Я жду фото, пришлите изображение.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_invoice:
        await update.message.reply_text("❌ Сначала пришлите номер накладной командой /start")
        return

    invoice_number = user_invoice[user_id]
    
    # Проверяем лимит фото на накладную
    current_photo_count = invoice_photo_count.get(invoice_number, 0)
    if current_photo_count >= MAX_PHOTOS_PER_INVOICE:
        await update.message.reply_text(
            f"❌ Достигнут лимит фото для накладной '{invoice_number}'\n\n"
            f"Максимум: {MAX_PHOTOS_PER_INVOICE} фото\n"
            f"Текущее количество: {current_photo_count}\n\n"
            f"Используйте /reset для сброса и начала новой накладной."
        )
        return
    
    photo_file = await update.message.photo[-1].get_file()
    
    # Проверка размера файла
    if photo_file.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(f"❌ Файл слишком большой!\n\nМаксимальный размер: {MAX_FILE_SIZE // (1024*1024)}MB\nТекущий размер: {photo_file.file_size // (1024*1024)}MB")
        return
    
    # Проверка формата файла
    if not photo_file.file_path or not photo_file.file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        await update.message.reply_text("❌ Неподдерживаемый формат файла!\n\nПоддерживаются только: JPG, JPEG, PNG")
        return

    # Создаем уникальное имя файла с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    safe_invoice = get_safe_folder_name(invoice_number)
    
    # Определяем расширение файла
    file_extension = '.jpg'  # По умолчанию
    if photo_file.file_path:
        if photo_file.file_path.lower().endswith('.png'):
            file_extension = '.png'
        elif photo_file.file_path.lower().endswith('.jpeg'):
            file_extension = '.jpeg'
    
    file_name = f"{timestamp}_{unique_id}{file_extension}"
    
    # Пути для загрузки
    folder_path = f"/{BASE_FOLDER}/{safe_invoice}"
    file_path = f"{folder_path}/{file_name}"

    # Создаем папку на Яндекс.Диске, если нет
    try:
        if not y.exists(folder_path):
            y.mkdir(folder_path)
            logger.info(f"✅ Создана папка на Яндекс.Диске: {folder_path}")
        else:
            logger.info(f"📁 Папка уже существует: {folder_path}")
            
        # Проверяем доступность папки для записи
        try:
            test_file_path = f"{folder_path}/.test_write"
            y.upload_string("test", test_file_path, overwrite=True)
            y.remove(test_file_path)
            logger.info(f"✅ Папка доступна для записи: {folder_path}")
        except Exception as write_test_error:
            logger.warning(f"⚠️ Проблема с правами записи в папку {folder_path}: {write_test_error}")
            await update.message.reply_text("⚠️ Предупреждение: возможны проблемы с правами записи в папку.")
            
    except yadisk.exceptions.YaDiskError as e:
        bot_stats["errors"] += 1
        error_msg = f"Ошибка Яндекс.Диска при создании папки: {e}"
        logger.error(error_msg)
        
        # Более детальные сообщения об ошибках
        if "quota" in str(e).lower():
            await update.message.reply_text("❌ Превышен лимит Яндекс.Диска\n\nОбратитесь к администратору для увеличения места.")
        elif "forbidden" in str(e).lower() or "access" in str(e).lower():
            await update.message.reply_text("❌ Нет доступа к Яндекс.Диску\n\nПроверьте токен и права доступа.")
        elif "network" in str(e).lower() or "timeout" in str(e).lower():
            await update.message.reply_text("❌ Проблема с сетью\n\nПопробуйте позже или проверьте интернет-соединение.")
        else:
            await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте позже или обратитесь к администратору.")
        return
    except Exception as e:
        bot_stats["errors"] += 1
        error_msg = f"Неожиданная ошибка при создании папки: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте позже или обратитесь к администратору.")
        return

    # Сохраняем фото во временный файл
    temp_path = f"/tmp/{photo_file.file_id}_{unique_id}{file_extension}"
    try:
        await photo_file.download_to_drive(temp_path)
        logger.info(f"📥 Файл загружен во временную папку: {temp_path}")
        
        # Проверяем, что файл действительно загрузился
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            raise Exception("Файл не был загружен или имеет нулевой размер")
            
    except Exception as e:
        bot_stats["errors"] += 1
        error_msg = f"Ошибка при загрузке файла: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте еще раз или отправьте файл меньшего размера.")
        return

    # Загружаем на Яндекс.Диск
    try:
        y.upload(temp_path, file_path, overwrite=True)
        bot_stats["total_photos"] += 1
        invoice_photo_count[invoice_number] = current_photo_count + 1
        
        logger.info(f"✅ Файл загружен на Яндекс.Диск: {file_path}")
        await update.message.reply_text(
            f"✅ Фото успешно сохранено!\n\n"
            f"📋 Накладная: {invoice_number}\n"
            f"📁 Папка: {BASE_FOLDER}/{safe_invoice}\n"
            f"📸 Файл: {file_name}\n"
            f"📏 Размер: {format_file_size(photo_file.file_size)}\n"
            f"📊 Фото в накладной: {invoice_photo_count[invoice_number]}/{MAX_PHOTOS_PER_INVOICE}"
        )
        
        # Предупреждение при приближении к лимиту
        if invoice_photo_count[invoice_number] >= MAX_PHOTOS_PER_INVOICE * 0.8:
            await update.message.reply_text(
                f"⚠️ Внимание! Приближается лимит фото для накладной '{invoice_number}'\n"
                f"Осталось: {MAX_PHOTOS_PER_INVOICE - invoice_photo_count[invoice_number]} фото"
            )
        
        # Показываем информацию о загруженном фото
        await update.message.reply_text(
            f"📸 Фото загружено! Всего в накладной: {invoice_photo_count[invoice_number]}/{MAX_PHOTOS_PER_INVOICE}\n\n"
            f"Продолжайте загружать фото или используйте /reset для завершения накладной."
        )
            
    except yadisk.exceptions.YaDiskError as e:
        bot_stats["errors"] += 1
        error_msg = f"Ошибка Яндекс.Диска при загрузке файла: {e}"
        logger.error(error_msg)
        
        # Более детальные сообщения об ошибках
        if "quota" in str(e).lower():
            await update.message.reply_text("❌ Превышен лимит Яндекс.Диска\n\nОбратитесь к администратору для увеличения места.")
        elif "network" in str(e).lower() or "timeout" in str(e).lower():
            await update.message.reply_text("❌ Проблема с сетью\n\nПопробуйте позже или проверьте интернет-соединение.")
        else:
            await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте позже или обратитесь к администратору.")
    except Exception as e:
        bot_stats["errors"] += 1
        error_msg = f"Неожиданная ошибка при загрузке на Яндекс.Диск: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте позже или обратитесь к администратору.")
    finally:
        # Удаляем локальный файл
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"🗑️ Временный файл удален: {temp_path}")
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {temp_path}: {e}")
            # Пытаемся удалить позже через cleanup

async def reset_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_invoice:
        old_invoice = user_invoice[user_id]
        old_photo_count = invoice_photo_count.get(old_invoice, 0)
        
        del user_invoice[user_id]
        if old_invoice in invoice_photo_count:
            del invoice_photo_count[old_invoice]
            
        await update.message.reply_text(
            f"🔄 Накладная '{old_invoice}' сброшена.\n"
            f"📸 Было загружено фото: {old_photo_count}\n\n"
            f"Пришлите новый номер накладной."
        )
    else:
        await update.message.reply_text("ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.")

def cleanup_temp_files():
    """Очищает временные файлы в /tmp"""
    try:
        temp_dir = "/tmp"
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                # Ищем файлы, созданные нашим ботом
                if (filename.endswith(('.jpg', '.jpeg', '.png')) and 
                    ('photo_file_' in filename or filename.count('_') >= 2)):
                    file_path = os.path.join(temp_dir, filename)
                    try:
                        # Удаляем файлы старше 1 часа
                        if os.path.getmtime(file_path) < (datetime.now().timestamp() - 3600):
                            os.remove(file_path)
                            logger.info(f"🗑️ Удален старый временный файл: {filename}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временный файл {filename}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при очистке временных файлов: {e}")

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для очистки временных файлов (только для администраторов)"""
    user_id = update.message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        cleanup_temp_files()
        await update.message.reply_text("✅ Временные файлы очищены.")
    except Exception as e:
        error_msg = f"Ошибка при очистке: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет пользователя в список разрешенных (только для администраторов)"""
    user_id = update.message.from_user.id
    
    # Проверяем права администратора
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите ID пользователя!\n\n"
            "Пример: /adduser 123456789\n\n"
            "Чтобы узнать ID пользователя, попросите его отправить /start боту @userinfobot"
        )
        return
    
    try:
        new_user_id = int(context.args[0])
        
        # Проверяем, что ID разумный
        if new_user_id <= 0:
            await update.message.reply_text("❌ ID пользователя должен быть положительным числом!")
            return
        
        # Добавляем пользователя
        if add_user_access(new_user_id):
            await update.message.reply_text(
                f"✅ Пользователь {new_user_id} добавлен в список разрешенных!\n\n"
                f"Теперь он может использовать бота."
            )
        else:
            await update.message.reply_text(f"ℹ️ Пользователь {new_user_id} уже имеет доступ к боту.")
            
    except ValueError:
        await update.message.reply_text("❌ ID пользователя должен быть числом!")
    except Exception as e:
        error_msg = f"Ошибка при добавлении пользователя: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет пользователя из списка разрешенных (только для администраторов)"""
    user_id = update.message.from_user.id
    
    # Проверяем права администратора
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите ID пользователя!\n\n"
            "Пример: /removeuser 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Проверяем, что ID разумный
        if target_user_id <= 0:
            await update.message.reply_text("❌ ID пользователя должен быть положительным числом!")
            return
        
        # Нельзя удалить самого себя
        if target_user_id == user_id:
            await update.message.reply_text("❌ Вы не можете удалить свой собственный доступ!")
            return
        
        # Удаляем пользователя
        if remove_user_access(target_user_id):
            await update.message.reply_text(
                f"✅ Пользователь {target_user_id} удален из списка разрешенных!\n\n"
                f"Теперь он не может использовать бота."
            )
        else:
            await update.message.reply_text(f"ℹ️ Пользователь {target_user_id} не найден в списке разрешенных.")
            
    except ValueError:
        await update.message.reply_text("❌ ID пользователя должен быть числом!")
    except Exception as e:
        error_msg = f"Ошибка при удалении пользователя: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех разрешенных пользователей (только для администраторов)"""
    user_id = update.message.from_user.id
    
    # Проверяем права администратора
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        if not ALLOWED_USERS:
            await update.message.reply_text("📋 Список разрешенных пользователей пуст.")
            return
        
        # Формируем список пользователей
        users_list = "📋 **Список разрешенных пользователей:**\n\n"
        
        for i, user_id in enumerate(sorted(ALLOWED_USERS), 1):
            # Определяем роль пользователя
            role = "👑 Администратор" if user_id in ADMIN_IDS else "👤 Пользователь"
            users_list += f"{i}. `{user_id}` - {role}\n"
        
        users_list += f"\n📊 **Всего пользователей:** {len(ALLOWED_USERS)}"
        
        await update.message.reply_text(users_list, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = f"Ошибка при получении списка пользователей: {e}"
        logger.error(error_msg)
        await update.message.reply_text(f"❌ {error_msg}")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о текущем пользователе"""
    user = update.message.from_user
    user_id = user.id
    
    # Проверяем права пользователя
    is_admin = user_id in ADMIN_IDS
    has_access = user_id in ALLOWED_USERS
    
    user_info_text = (
        f"👤 **Информация о пользователе**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {user.first_name or 'Не указано'}\n"
        f"📝 Фамилия: {user.last_name or 'Не указана'}\n"
        f"🔗 Username: @{user.username or 'Не указан'}\n\n"
        f"🔐 **Права доступа:**\n"
        f"• Доступ к боту: {'✅ Да' if has_access else '❌ Нет'}\n"
        f"• Администратор: {'✅ Да' if is_admin else '❌ Нет'}\n\n"
    )
    
    if has_access:
        # Показываем информацию о накладной
        if user_id in user_invoice:
            invoice_number = user_invoice[user_id]
            photo_count = invoice_photo_count.get(invoice_number, 0)
            user_info_text += (
                f"📋 **Текущая накладная:**\n"
                f"• Номер: {invoice_number}\n"
                f"• Загружено фото: {photo_count}/{MAX_PHOTOS_PER_INVOICE}\n"
            )
        else:
            user_info_text += "📋 **Текущая накладная:** Нет активной накладной\n"
    
    if is_admin:
        user_info_text += (
            f"\n👑 **Административные команды:**\n"
            f"• /adduser <ID> - Добавить пользователя\n"
            f"• /removeuser <ID> - Удалить пользователя\n"
            f"• /listusers - Список пользователей\n"
            f"• /cleanup - Очистка временных файлов"
        )
    
    await update.message.reply_text(user_info_text, parse_mode='Markdown')

def main():
    logger.info("🚀 Запуск Telegram бота...")
    
    try:
        # Загружаем список разрешенных пользователей
        global ALLOWED_USERS
        ALLOWED_USERS = load_allowed_users()
        logger.info(f"👥 Загружено {len(ALLOWED_USERS)} разрешенных пользователей")
        
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Добавляем обработчик ошибок
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Обработчик ошибок для логирования исключений"""
            logger.error(f"❌ Ошибка при обработке обновления: {context.error}")
            if update and hasattr(update, 'message') and update.message:
                try:
                    await update.message.reply_text(
                        "❌ Произошла ошибка при обработке сообщения.\n"
                        "Попробуйте еще раз или обратитесь к администратору."
                    )
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")

        app.add_error_handler(error_handler)

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("reset", reset_invoice))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("current", current_invoice))
        app.add_handler(CommandHandler("cleanup", cleanup))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("adduser", add_user))
        app.add_handler(CommandHandler("removeuser", remove_user))
        app.add_handler(CommandHandler("listusers", list_users))
        app.add_handler(CommandHandler("userinfo", user_info))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        logger.info("✅ Все обработчики команд зарегистрированы")
        logger.info(f"🌐 Запуск webhook на порту {os.environ.get('PORT', 8443)}")
        logger.info(f"🔗 Webhook URL: {os.environ.get('WEBHOOK_URL', 'https://gidromag-bot.onrender.com/')}")

        # Запуск webhook на Render
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://gidromag-bot.onrender.com/")
        app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main()
