import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime

import database as db
from config import BASE_FOLDER
from services import yadisk_service

logger = logging.getLogger(__name__)

REMOTE_STATS_PATH = f"/{BASE_FOLDER}/bot_stats.json"
_SAVE_INTERVAL = 900  # 15 минут


async def load_from_remote() -> None:
    """Load stats from Yandex.Disk into SQLite on startup."""
    try:
        if not await yadisk_service.exists(REMOTE_STATS_PATH):
            logger.info("ℹ️ Файл статистики на Яндекс.Диске не найден, начинаем с нуля")
            return
        tmp = os.path.join(tempfile.gettempdir(), f"bot_stats_{uuid.uuid4().hex}.json")
        await yadisk_service.download(REMOTE_STATS_PATH, tmp)
        with open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        try:
            os.remove(tmp)
        except Exception:
            pass
        stat_keys = ('total_photos', 'total_videos', 'total_documents', 'total_invoices', 'errors')
        for key in stat_keys:
            if key in data and isinstance(data[key], int) and data[key] > 0:
                current = await db.get_stat(key)
                if data[key] > current:
                    # Set the value from remote (it's higher = more up-to-date)
                    await db.increment_stat(key, data[key] - current)
        logger.info(
            f"✅ Статистика восстановлена с Яндекс.Диска: "
            f"фото={data.get('total_photos',0)}, "
            f"видео={data.get('total_videos',0)}, "
            f"документы={data.get('total_documents',0)}, "
            f"накладные={data.get('total_invoices',0)}"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить статистику с Яндекс.Диска: {e}")


async def save_to_remote() -> bool:
    """Save current stats from SQLite to Yandex.Disk."""
    try:
        stats = await db.get_all_stats()
        stats['last_saved'] = datetime.now().isoformat(timespec='seconds')
        content = json.dumps(stats, ensure_ascii=False, indent=2)
        tmp = os.path.join(tempfile.gettempdir(), f"bot_stats_{uuid.uuid4().hex}.json")
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(content)
        try:
            await yadisk_service.ensure_folder(f"/{BASE_FOLDER}")
            await yadisk_service.upload(tmp, REMOTE_STATS_PATH, overwrite=True)
            logger.info("💾 Статистика сохранена на Яндекс.Диск")
            return True
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сохранить статистику на Яндекс.Диск: {e}")
        return False


async def start_periodic_save_task() -> None:
    """Background task: save stats to Yandex.Disk every 15 minutes."""
    while True:
        await asyncio.sleep(_SAVE_INTERVAL)
        await save_to_remote()
