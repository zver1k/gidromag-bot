import logging
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from config import (
    ADMIN_IDS, BASE_FOLDER, INVOICE_PATTERN,
    MAX_FILE_SIZE, MAX_VIDEO_SIZE, MAX_DOCUMENT_SIZE,
    MAX_PHOTOS_PER_INVOICE, MAX_VIDEOS_PER_INVOICE, MAX_DOCUMENTS_PER_INVOICE,
    INFO_MESSAGES,
)
from services import session_service, users_service

logger = logging.getLogger(__name__)

_INVOICE_RE = re.compile(INVOICE_PATTERN)
_bot_start_time = datetime.now()


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size // 1024} KB"
    return f"{size // (1024 * 1024)} MB"


def get_uptime() -> str:
    delta = datetime.now() - _bot_start_time
    d, rem = divmod(delta.seconds + delta.days * 86400, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d > 0:
        return f"{d}д {h}ч {m}м"
    elif h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def get_safe_folder_name(invoice: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', invoice)


def get_menu_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    has_invoice = user_id is not None and user_id in session_service.user_invoice
    if not has_invoice:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать накладную", callback_data="menu_create")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
        ])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Текущая накладная", callback_data="menu_current"),
            InlineKeyboardButton("🔄 Сбросить накладную", callback_data="menu_reset"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
        ],
    ])


def get_effective_message(update: Update):
    if update.message:
        return update.message
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message
    return None


def validate_invoice(text: str) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "Номер накладной не может быть пустым"
    text = text.strip()
    if len(text) < 3:
        return False, "Минимум 3 символа"
    if len(text) > 50:
        return False, "Максимум 50 символов"
    if not _INVOICE_RE.match(text):
        return False, "Недопустимые символы. Разрешены: буквы, цифры, пробел, дефис, подчёркивание"
    return True, ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not users_service.is_allowed(user_id):
        if await users_service.refresh_from_remote() and users_service.is_allowed(user_id):
            pass
        else:
            await update.message.reply_text("❌ У вас нет прав для использования бота.")
            return
    session_service.touch(user_id)
    await update.message.reply_text(
        "Привет! Пришли номер накладной:\n\n"
        "📸 Загружайте фото и видео оборудования. Используйте /reset для завершения накладной.",
        reply_markup=get_menu_keyboard(user_id)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"📝 Сообщение от {user_id}: '{text}'")

    if session_service.is_expired(user_id):
        was_active, *_ = await session_service.reset(user_id)
        if was_active:
            await update.message.reply_text(INFO_MESSAGES["session_expired"])

    if not users_service.is_allowed(user_id):
        if await users_service.refresh_from_remote() and users_service.is_allowed(user_id):
            pass
        else:
            await update.message.reply_text("❌ У вас нет прав для использования бота.")
            return

    is_valid, error = validate_invoice(text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error}\n\nПопробуйте ещё раз или используйте /reset.",
            reply_markup=get_menu_keyboard(user_id)
        )
        return

    if user_id not in session_service.user_invoice:
        await session_service.create(user_id, text.strip())
        await update.message.reply_text(
            f"✅ Накладная '{text.strip()}' сохранена.\n\nТеперь пришлите фото, видео или документы.",
            reply_markup=get_menu_keyboard(user_id)
        )
    else:
        await update.message.reply_text(
            "📸 Я жду файл, пришлите фото, видео или документ.",
            reply_markup=get_menu_keyboard(user_id)
        )
    session_service.touch(user_id)


async def reset_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id
    was_active, invoice, p, v, d = await session_service.reset(user_id)
    if was_active:
        await message.reply_text(
            f"🔄 Накладная '{invoice}' сброшена.\n"
            f"📸 Загружено фото: {p}\n🎥 Загружено видео: {v}\n📄 Загружено документов: {d}\n\n"
            f"Пришлите новый номер накладной.",
            reply_markup=get_menu_keyboard(user_id)
        )
    else:
        await message.reply_text(
            "ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.",
            reply_markup=get_menu_keyboard(user_id)
        )
    session_service.touch(user_id)


async def current_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id
    if user_id not in session_service.user_invoice:
        await message.reply_text(
            "ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.",
            reply_markup=get_menu_keyboard(user_id)
        )
        return
    inv = session_service.user_invoice[user_id]
    p = session_service.invoice_photo_count.get(inv, 0)
    v = session_service.invoice_video_count.get(inv, 0)
    d = session_service.invoice_document_count.get(inv, 0)
    rp, rv, rd = MAX_PHOTOS_PER_INVOICE - p, MAX_VIDEOS_PER_INVOICE - v, MAX_DOCUMENTS_PER_INVOICE - d
    if p == v == d == 0:
        status = "📸 Отправьте первый файл"
    elif rp <= 0 and rv <= 0 and rd <= 0:
        status = "❌ Лимит достигнут. Используйте /reset"
    elif rp <= 5 or rv <= 2 or rd <= 5:
        status = f"⚠️ Осталось мало: {rp} фото, {rv} видео, {rd} документов"
    else:
        status = f"✅ Можно ещё: {rp} фото, {rv} видео, {rd} документов"
    await message.reply_text(
        f"📋 **Текущая накладная**\n\n"
        f"🔢 Номер: {inv}\n"
        f"📸 Фото: {p}/{MAX_PHOTOS_PER_INVOICE}\n"
        f"🎥 Видео: {v}/{MAX_VIDEOS_PER_INVOICE}\n"
        f"📄 Документы: {d}/{MAX_DOCUMENTS_PER_INVOICE}\n"
        f"📁 Папка: {BASE_FOLDER}/{get_safe_folder_name(inv)}\n\n{status}",
        parse_mode='Markdown',
        reply_markup=get_menu_keyboard(user_id)
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id
    all_stats = await db.get_all_stats()
    active = len(session_service.user_invoice)
    unique_inv = len(set(session_service.user_invoice.values()))
    p_inv = sum(session_service.invoice_photo_count.values())
    v_inv = sum(session_service.invoice_video_count.values())
    d_inv = sum(session_service.invoice_document_count.values())
    await message.reply_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"⏱️ Время работы: {get_uptime()}\n"
        f"👥 Активных пользователей: {active}\n"
        f"📋 Активных накладных: {unique_inv}\n"
        f"📸 Всего загружено фото: {all_stats.get('total_photos', 0)}\n"
        f"🎥 Всего загружено видео: {all_stats.get('total_videos', 0)}\n"
        f"📄 Всего загружено документов: {all_stats.get('total_documents', 0)}\n"
        f"📸 Фото в накладных: {p_inv}\n"
        f"🎥 Видео в накладных: {v_inv}\n"
        f"📄 Документы в накладных: {d_inv}\n"
        f"📋 Всего накладных: {all_stats.get('total_invoices', 0)}\n"
        f"❌ Ошибок: {all_stats.get('errors', 0)}\n\n"
        f"🔄 /reset — сбросить накладную\n"
        f"🔍 /status — проверить сервисы",
        parse_mode='HTML',
        reply_markup=get_menu_keyboard(user_id)
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id
    from services import yadisk_service
    disk = await yadisk_service.get_disk_info()
    base_exists = await yadisk_service.exists(f"/{BASE_FOLDER}")
    text = (
        f"🔍 <b>Статус бота</b>\n\n"
        f"✅ <b>Telegram Bot</b>: Активен\n"
        f"✅ <b>Яндекс.Диск</b>: Подключен\n"
        f"📁 <b>Базовая папка</b>: {'Существует' if base_exists else 'Не найдена'}\n\n"
    )
    if disk['available']:
        used_pct = round((disk['total'] - disk['free']) / disk['total'] * 100, 1) if disk['total'] else 0
        text += (
            f"💾 <b>Место на диске:</b>\n"
            f"• Свободно: {format_file_size(disk['free'])}\n"
            f"• Всего: {format_file_size(disk['total'])}\n"
            f"• Использовано: {used_pct}%\n\n"
        )
    else:
        text += "💾 <b>Место на диске:</b> Информация недоступна\n\n"
    all_stats = await db.get_all_stats()
    text += (
        f"📊 <b>Статистика:</b>\n"
        f"• Фото: {all_stats.get('total_photos', 0)}\n"
        f"• Видео: {all_stats.get('total_videos', 0)}\n"
        f"• Документы: {all_stats.get('total_documents', 0)}\n"
        f"• Накладные: {all_stats.get('total_invoices', 0)}\n"
        f"• Ошибки: {all_stats.get('errors', 0)}"
    )
    await message.reply_text(text, parse_mode='HTML', reply_markup=get_menu_keyboard(user_id))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id
    await message.reply_text(
        f"🤖 <b>Справка по командам</b>\n\n"
        f"📋 <b>Основные команды:</b>\n"
        f"• /start — Начать работу с новой накладной\n"
        f"• /reset — Сбросить текущую накладную\n"
        f"• /current — Показать текущую накладную\n"
        f"• /stats — Статистика бота\n"
        f"• /status — Статус бота и сервисов\n"
        f"• /help — Эта справка\n"
        f"• /userinfo — Информация о пользователе\n\n"
        f"👑 <b>Административные команды:</b>\n"
        f"• /adduser &lt;ID&gt; — Добавить пользователя\n"
        f"• /removeuser &lt;ID&gt; — Удалить пользователя\n"
        f"• /listusers — Список пользователей\n"
        f"• /cleanup — Очистка временных файлов\n\n"
        f"📋 <b>Как использовать:</b>\n"
        f"1. Отправьте /start\n"
        f"2. Введите номер накладной\n"
        f"3. Отправьте фото, видео или документы\n"
        f"4. Файлы сохраняются на Яндекс.Диск\n"
        f"5. /reset для завершения накладной\n\n"
        f"⚠️ <b>Ограничения:</b>\n"
        f"• Фото: до {format_file_size(MAX_FILE_SIZE)}, макс {MAX_PHOTOS_PER_INVOICE} шт.\n"
        f"• Видео: до {format_file_size(MAX_VIDEO_SIZE)}, макс {MAX_VIDEOS_PER_INVOICE} шт.\n"
        f"• Документы: до {format_file_size(MAX_DOCUMENT_SIZE)}, макс {MAX_DOCUMENTS_PER_INVOICE} шт.\n"
        f"• Форматы фото: JPG, JPEG, PNG\n"
        f"• Форматы видео: MP4, AVI, MOV, MKV, WMV, FLV, WEBM, M4V\n"
        f"• Форматы документов: PDF, DOC, DOCX, XLS, XLSX\n\n"
        f"💡 ID пользователя: /start в @userinfobot",
        parse_mode='HTML',
        reply_markup=get_menu_keyboard(user_id)
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id if update.effective_user else None
    await message.reply_text("🛠️ Выберите действие:", reply_markup=get_menu_keyboard(user_id))


async def prompt_invoice_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_effective_message(update)
    if not message:
        return
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and user_id in session_service.user_invoice:
        await message.reply_text(
            "ℹ️ У вас уже есть активная накладная.",
            reply_markup=get_menu_keyboard(user_id)
        )
        return
    await message.reply_text(
        "✍️ Отправьте номер накладной (3–50 символов: буквы, цифры, пробел, дефис, подчёркивание).",
        reply_markup=get_menu_keyboard(user_id)
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    dispatch = {
        "menu_current": current_invoice,
        "menu_reset": reset_invoice,
        "menu_stats": stats,
        "menu_help": help_command,
        "menu_create": prompt_invoice_creation,
    }
    handler = dispatch.get(data)
    if handler:
        await handler(update, context)
    elif query.message:
        await query.message.reply_text("❓ Неизвестная команда.")


async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    is_admin = uid in ADMIN_IDS
    has_access = users_service.is_allowed(uid)
    text = (
        f"👤 **Информация о пользователе**\n\n"
        f"🆔 ID: `{uid}`\n"
        f"👤 Имя: {user.first_name or 'Не указано'}\n"
        f"📝 Фамилия: {user.last_name or 'Не указана'}\n"
        f"🔗 Username: @{user.username or 'Не указан'}\n\n"
        f"🔐 **Права доступа:**\n"
        f"• Доступ к боту: {'✅ Да' if has_access else '❌ Нет'}\n"
        f"• Администратор: {'✅ Да' if is_admin else '❌ Нет'}\n\n"
    )
    if has_access and uid in session_service.user_invoice:
        inv = session_service.user_invoice[uid]
        text += (
            f"📋 **Текущая накладная:**\n"
            f"• Номер: {inv}\n"
            f"• Фото: {session_service.invoice_photo_count.get(inv, 0)}/{MAX_PHOTOS_PER_INVOICE}\n"
            f"• Видео: {session_service.invoice_video_count.get(inv, 0)}/{MAX_VIDEOS_PER_INVOICE}\n"
            f"• Документы: {session_service.invoice_document_count.get(inv, 0)}/{MAX_DOCUMENTS_PER_INVOICE}\n"
        )
    elif has_access:
        text += "📋 **Текущая накладная:** Нет активной накладной\n"
    if is_admin:
        text += "\n👑 **Административные команды:**\n• /adduser /removeuser /listusers /cleanup"
    await update.message.reply_text(text, parse_mode='Markdown')
