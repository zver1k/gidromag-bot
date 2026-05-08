import asyncio
import logging
import os
import uuid

from config import ADMIN_IDS, BASE_FOLDER
from services import yadisk_service

logger = logging.getLogger(__name__)

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "allowed_users.txt")
REMOTE_USERS_PATH = f"/{BASE_FOLDER}/allowed_users.txt"

_users_lock = asyncio.Lock()
ALLOWED_USERS: list[int] = []


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS or user_id in ADMIN_IDS


async def _upload_users_text(content: str) -> None:
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), f"upload_text_{uuid.uuid4().hex}.txt")
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    try:
        await yadisk_service.upload(tmp, REMOTE_USERS_PATH, overwrite=True)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


async def save(users: list[int]) -> bool:
    try:
        content = "".join(f"{uid}\n" for uid in sorted(users))
        base = f"/{BASE_FOLDER}"
        await yadisk_service.ensure_folder(base)
        await _upload_users_text(content)
        logger.info("✅ Список пользователей сохранён на Яндекс.Диске")
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователей: {e}")
        return False


async def refresh_from_remote() -> bool:
    """Pull latest allowed_users.txt from Yandex.Disk into ALLOWED_USERS."""
    global ALLOWED_USERS
    import tempfile
    try:
        if await yadisk_service.exists(REMOTE_USERS_PATH):
            tmp = os.path.join(tempfile.gettempdir(), f"allowed_users_{uuid.uuid4().hex}.txt")
            await yadisk_service.download(REMOTE_USERS_PATH, tmp)
            with open(tmp, 'r', encoding='utf-8') as f:
                users = [int(line.strip()) for line in f if line.strip().isdigit()]
            try:
                os.remove(tmp)
            except Exception:
                pass
            if users:
                ALLOWED_USERS = sorted(set(users))
                logger.info(f"🔄 Обновлен список пользователей: {len(ALLOWED_USERS)}")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Не удалось обновить список пользователей: {e}")
    return False


async def load() -> None:
    """Load users on startup: remote → local fallback."""
    global ALLOWED_USERS
    import tempfile
    try:
        if await yadisk_service.exists(REMOTE_USERS_PATH):
            tmp = os.path.join(tempfile.gettempdir(), f"allowed_users_{uuid.uuid4().hex}.txt")
            await yadisk_service.download(REMOTE_USERS_PATH, tmp)
            with open(tmp, 'r', encoding='utf-8') as f:
                users = [int(line.strip()) for line in f if line.strip().isdigit()]
            try:
                os.remove(tmp)
            except Exception:
                pass
            ALLOWED_USERS = sorted(set(users))
            logger.info(f"✅ Загружено {len(ALLOWED_USERS)} пользователей с Яндекс.Диска")
            return
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить с Яндекс.Диска: {e}")

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            ALLOWED_USERS = sorted({int(l.strip()) for l in f if l.strip().isdigit()})
        logger.info(f"✅ Загружено {len(ALLOWED_USERS)} пользователей (локально)")
        return

    await save(list(ADMIN_IDS))
    ALLOWED_USERS = list(ADMIN_IDS)


async def add(user_id: int) -> bool:
    global ALLOWED_USERS
    async with _users_lock:
        if user_id not in ALLOWED_USERS:
            ALLOWED_USERS.append(user_id)
            await save(ALLOWED_USERS)
            logger.info(f"✅ Добавлен доступ для {user_id}")
            return True
    return False


async def remove(user_id: int) -> bool:
    global ALLOWED_USERS
    async with _users_lock:
        if user_id in ALLOWED_USERS:
            ALLOWED_USERS.remove(user_id)
            await save(ALLOWED_USERS)
            logger.info(f"✅ Удалён доступ для {user_id}")
            return True
    return False
