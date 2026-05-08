import logging
import os
import tempfile
import uuid
from datetime import datetime

import yadisk.exceptions
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

import database as db
from config import (
    BASE_FOLDER,
    MAX_FILE_SIZE, MAX_VIDEO_SIZE, MAX_DOCUMENT_SIZE,
    MAX_PHOTOS_PER_INVOICE, MAX_VIDEOS_PER_INVOICE, MAX_DOCUMENTS_PER_INVOICE,
    SUPPORTED_PHOTO_FORMATS, SUPPORTED_VIDEO_FORMATS, SUPPORTED_DOCUMENT_FORMATS,
    INFO_MESSAGES,
)
from handlers.commands import get_menu_keyboard, get_safe_folder_name, format_file_size
from services import session_service, users_service, yadisk_service
from utils import rate_limiter, image_utils

logger = logging.getLogger(__name__)


async def _check_session(update: Update, user_id: int) -> bool:
    if session_service.is_expired(user_id):
        was_active, *_ = await session_service.reset(user_id)
        if was_active:
            await update.message.reply_text(INFO_MESSAGES["session_expired"])
        await update.message.reply_text(
            "ℹ️ У вас нет активной накладной.\n\nИспользуйте /start для начала работы.",
            reply_markup=get_menu_keyboard(user_id)
        )
        session_service.touch(user_id)
        return False
    if user_id not in session_service.user_invoice:
        await update.message.reply_text(
            "❌ Сначала пришлите номер накладной командой /start",
            reply_markup=get_menu_keyboard(user_id)
        )
        session_service.touch(user_id)
        return False
    return True


async def _upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_obj,
    invoice_number: str,
    file_type: str,
    max_count: int,
    max_size: int,
    supported_formats: list[str],
    default_ext: str,
    emoji: str,
    stat_key: str,
    limit_label: str,
) -> None:
    user_id = update.message.from_user.id

    # Rate limiting
    allowed, wait = await rate_limiter.check(user_id)
    if not allowed:
        await update.message.reply_text(
            f"⏱ Слишком много загрузок. Подождите {wait} сек. и попробуйте снова."
        )
        return

    file_size = file_obj.file_size or 0

    if file_size > max_size:
        await update.message.reply_text(
            f"❌ Файл слишком большой!\n\n"
            f"Максимум: {format_file_size(max_size)}\n"
            f"Текущий: {format_file_size(file_size)}"
        )
        return

    if file_obj.file_path and not any(file_obj.file_path.lower().endswith(f) for f in supported_formats):
        fmt_list = ", ".join(f.lstrip(".").upper() for f in supported_formats)
        await update.message.reply_text(f"❌ Неподдерживаемый формат!\n\nПоддерживаются: {fmt_list}")
        return

    ext = default_ext
    if file_obj.file_path:
        for fmt in supported_formats:
            if file_obj.file_path.lower().endswith(fmt):
                ext = fmt
                break

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    safe_invoice = get_safe_folder_name(invoice_number)
    file_name = f"{timestamp}_{unique_id}{ext}"
    folder_path = f"/{BASE_FOLDER}/{safe_invoice}"
    remote_path = f"{folder_path}/{file_name}"

    # Ensure folder exists
    try:
        await yadisk_service.ensure_folder(folder_path)
    except yadisk.exceptions.YaDiskError as e:
        await db.increment_stat('errors')
        err = str(e).lower()
        if 'quota' in err:
            await update.message.reply_text("❌ Превышен лимит Яндекс.Диска.\n\nОбратитесь к администратору.")
        elif 'forbidden' in err or 'access' in err:
            await update.message.reply_text("❌ Нет доступа к Яндекс.Диску.")
        else:
            await update.message.reply_text(f"❌ Ошибка Яндекс.Диска: {e}\n\nПопробуйте позже.")
        return

    # Typing indicator
    try:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    except Exception:
        pass

    tmp_dir = tempfile.gettempdir()
    temp_path = os.path.join(tmp_dir, f"{file_obj.file_id}_{unique_id}{ext}")

    try:
        await file_obj.download_to_drive(temp_path)
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            raise ValueError("Файл не загружен или имеет нулевой размер")
    except Exception as e:
        await db.increment_stat('errors')
        await update.message.reply_text(f"❌ Ошибка при скачивании файла: {e}\n\nПопробуйте ещё раз.")
        return

    # Deduplication
    file_hash = image_utils.compute_md5(temp_path)
    if await db.is_duplicate(invoice_number, file_hash):
        os.remove(temp_path)
        await update.message.reply_text(
            "⚠️ Этот файл уже загружен в данную накладную.\n\nПришлите другой файл."
        )
        return

    # Image compression (photos only)
    upload_path = temp_path
    compressed_path = None
    if file_type == 'photo':
        compressed_path = os.path.join(tmp_dir, f"compressed_{unique_id}.jpg")
        if image_utils.compress_photo(temp_path, compressed_path):
            upload_path = compressed_path
            file_size = os.path.getsize(compressed_path)

    try:
        await yadisk_service.upload(upload_path, remote_path)
        await db.add_file_hash(invoice_number, file_hash, file_name, datetime.now().timestamp())
        await db.increment_stat(stat_key)
        new_count = await session_service.increment_file_count(invoice_number, file_type)
        remaining = max_count - new_count
        warning = (
            f"\n\n⚠️ Осталось {limit_label}: {remaining} — скоро лимит!"
            if new_count >= max_count * 0.8
            else f"\n\nПродолжайте загружать или /reset для завершения."
        )
        await update.message.reply_text(
            f"✅ Файл сохранён!\n"
            f"📋 Накладная: {invoice_number}\n"
            f"{emoji} Файл: {file_name}\n"
            f"📏 Размер: {format_file_size(file_size)}\n"
            f"📊 В накладной: {new_count}/{max_count}"
            f"{warning}"
        )
        logger.info(f"✅ Загружено: {remote_path}")
    except yadisk.exceptions.YaDiskError as e:
        await db.increment_stat('errors')
        err = str(e).lower()
        if 'quota' in err:
            await update.message.reply_text("❌ Превышен лимит Яндекс.Диска.")
        elif 'network' in err or 'timeout' in err:
            await update.message.reply_text("❌ Проблема с сетью. Попробуйте позже.")
        else:
            await update.message.reply_text(f"❌ Ошибка при загрузке: {e}\n\nПопробуйте позже.")
    except Exception as e:
        await db.increment_stat('errors')
        logger.error(f"Неожиданная ошибка при загрузке: {e}")
        await update.message.reply_text(f"❌ Неожиданная ошибка: {e}\n\nПопробуйте позже.")
    finally:
        for path in (temp_path, compressed_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await _check_session(update, user_id):
        return
    invoice = session_service.user_invoice[user_id]
    if session_service.invoice_photo_count.get(invoice, 0) >= MAX_PHOTOS_PER_INVOICE:
        await update.message.reply_text(
            f"❌ Лимит фото достигнут ({MAX_PHOTOS_PER_INVOICE}). Используйте /reset."
        )
        return
    file_obj = await update.message.photo[-1].get_file()
    await _upload(
        update, context, file_obj, invoice, 'photo',
        MAX_PHOTOS_PER_INVOICE, MAX_FILE_SIZE, SUPPORTED_PHOTO_FORMATS,
        ".jpg", "📸", "total_photos", "фото"
    )
    session_service.touch(user_id)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await _check_session(update, user_id):
        return
    invoice = session_service.user_invoice[user_id]
    if session_service.invoice_video_count.get(invoice, 0) >= MAX_VIDEOS_PER_INVOICE:
        await update.message.reply_text(
            f"❌ Лимит видео достигнут ({MAX_VIDEOS_PER_INVOICE}). Используйте /reset."
        )
        return
    file_obj = await update.message.video.get_file()
    await _upload(
        update, context, file_obj, invoice, 'video',
        MAX_VIDEOS_PER_INVOICE, MAX_VIDEO_SIZE, SUPPORTED_VIDEO_FORMATS,
        ".mp4", "🎥", "total_videos", "видео"
    )
    session_service.touch(user_id)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await _check_session(update, user_id):
        return
    invoice = session_service.user_invoice[user_id]
    if session_service.invoice_document_count.get(invoice, 0) >= MAX_DOCUMENTS_PER_INVOICE:
        await update.message.reply_text(
            f"❌ Лимит документов достигнут ({MAX_DOCUMENTS_PER_INVOICE}). Используйте /reset."
        )
        return
    file_obj = await update.message.document.get_file()
    await _upload(
        update, context, file_obj, invoice, 'document',
        MAX_DOCUMENTS_PER_INVOICE, MAX_DOCUMENT_SIZE, SUPPORTED_DOCUMENT_FORMATS,
        ".pdf", "📄", "total_documents", "документов"
    )
    session_service.touch(user_id)
