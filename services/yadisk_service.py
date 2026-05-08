import asyncio
import logging
import yadisk
import yadisk.exceptions

from config import YANDEX_DISK_TOKEN

logger = logging.getLogger(__name__)

y = yadisk.YaDisk(token=YANDEX_DISK_TOKEN)

_RETRY_DELAYS = [1, 2, 4]
_NO_RETRY_KEYWORDS = ('auth', 'forbidden', 'quota', 'unauthorized', '401', '403')


def _is_retryable(e: Exception) -> bool:
    msg = str(e).lower()
    return not any(kw in msg for kw in _NO_RETRY_KEYWORDS)


async def _run(func, *args, **kwargs):
    """Run a sync yadisk call in a thread with retry on transient errors."""
    last_exc = None
    for attempt, delay in enumerate(_RETRY_DELAYS, 1):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except yadisk.exceptions.YaDiskError as e:
            last_exc = e
            if not _is_retryable(e):
                raise
            logger.warning(f"⚠️ Яндекс.Диск ошибка (попытка {attempt}/{len(_RETRY_DELAYS)}): {e}")
            if attempt < len(_RETRY_DELAYS):
                await asyncio.sleep(delay)
        except Exception as e:
            last_exc = e
            logger.warning(f"⚠️ Сетевая ошибка (попытка {attempt}/{len(_RETRY_DELAYS)}): {e}")
            if attempt < len(_RETRY_DELAYS):
                await asyncio.sleep(delay)
    raise last_exc


async def exists(path: str) -> bool:
    return await _run(y.exists, path)


async def mkdir(path: str) -> None:
    await _run(y.mkdir, path)


async def upload(local_path: str, remote_path: str, overwrite: bool = True) -> None:
    await _run(y.upload, local_path, remote_path, overwrite=overwrite)


async def download(remote_path: str, local_path: str) -> None:
    await _run(y.download, remote_path, local_path)


async def get_disk_info() -> dict:
    try:
        info = await _run(y.get_disk_info)
        if hasattr(info, 'space') and hasattr(info.space, 'free'):
            return {'free': info.space.free, 'total': info.space.total, 'available': True}
        elif hasattr(info, 'free'):
            return {'free': info.free, 'total': info.total, 'available': True}
        elif hasattr(info, 'available'):
            return {'free': info.available, 'total': getattr(info, 'total', 0), 'available': True}
        return {'free': 0, 'total': 0, 'available': False}
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о диске: {e}")
        return {'free': 0, 'total': 0, 'available': False}


async def ensure_folder(path: str) -> None:
    if not await exists(path):
        await mkdir(path)
