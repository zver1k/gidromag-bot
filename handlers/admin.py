import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from services import users_service

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите ID пользователя!\n\nПример: /adduser 123456789"
        )
        return
    try:
        new_id = int(context.args[0])
        if new_id <= 0:
            await update.message.reply_text("❌ ID должен быть положительным числом!")
            return
        if await users_service.add(new_id):
            logger.info(f"[AUDIT] Администратор {user_id} добавил пользователя {new_id}")
            await update.message.reply_text(f"✅ Пользователь {new_id} добавлен.")
        else:
            await update.message.reply_text(f"ℹ️ Пользователь {new_id} уже имеет доступ.")
    except ValueError:
        await update.message.reply_text("❌ ID пользователя должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя!\n\nПример: /removeuser 123456789")
        return
    try:
        target_id = int(context.args[0])
        if target_id <= 0:
            await update.message.reply_text("❌ ID должен быть положительным числом!")
            return
        if target_id == user_id:
            await update.message.reply_text("❌ Нельзя удалить себя!")
            return
        if await users_service.remove(target_id):
            logger.info(f"[AUDIT] Администратор {user_id} удалил пользователя {target_id}")
            await update.message.reply_text(f"✅ Пользователь {target_id} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ Пользователь {target_id} не найден в списке.")
    except ValueError:
        await update.message.reply_text("❌ ID пользователя должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    if not users_service.ALLOWED_USERS:
        await update.message.reply_text("📋 Список разрешённых пользователей пуст.")
        return
    lines = []
    for i, uid in enumerate(sorted(users_service.ALLOWED_USERS), 1):
        role = "👑 Администратор" if uid in ADMIN_IDS else "👤 Пользователь"
        lines.append(f"{i}. `{uid}` — {role}")
    text = "📋 **Список разрешённых пользователей:**\n\n" + "\n".join(lines)
    text += f"\n\n📊 **Всего:** {len(users_service.ALLOWED_USERS)}"
    await update.message.reply_text(text, parse_mode='Markdown')


async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    try:
        tmp_dir = tempfile.gettempdir()
        exts = {'.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mov', '.mkv', '.wmv',
                '.flv', '.webm', '.m4v', '.3gp', '.pdf', '.doc', '.docx', '.xls', '.xlsx'}
        removed = 0
        for fname in os.listdir(tmp_dir):
            if any(fname.lower().endswith(e) for e in exts):
                fpath = os.path.join(tmp_dir, fname)
                try:
                    os.remove(fpath)
                    removed += 1
                except Exception:
                    pass
        await update.message.reply_text(f"✅ Очищено временных файлов: {removed}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при очистке: {e}")
