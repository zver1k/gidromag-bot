import asyncio
import logging
from datetime import datetime

import database as db
from config import INACTIVITY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# In-memory state (backed by SQLite)
user_invoice: dict[int, str] = {}
user_last_activity: dict[int, datetime] = {}
invoice_photo_count: dict[str, int] = {}
invoice_video_count: dict[str, int] = {}
invoice_document_count: dict[str, int] = {}


async def load_from_db() -> None:
    """Restore sessions from DB on startup."""
    rows = await db.load_all_sessions()
    for user_id, invoice_number, updated_at in rows:
        user_invoice[user_id] = invoice_number
        user_last_activity[user_id] = datetime.fromtimestamp(updated_at)
        p, v, d = await db.get_invoice_files(invoice_number)
        invoice_photo_count[invoice_number] = p
        invoice_video_count[invoice_number] = v
        invoice_document_count[invoice_number] = d
    logger.info(f"✅ Восстановлено {len(rows)} сессий из базы данных")


def is_expired(user_id: int) -> bool:
    last = user_last_activity.get(user_id)
    if not last:
        return False
    return (datetime.now() - last).total_seconds() > INACTIVITY_TIMEOUT_SECONDS


def touch(user_id: int) -> None:
    user_last_activity[user_id] = datetime.now()
    asyncio.ensure_future(
        db.upsert_session(user_id, user_invoice.get(user_id, ''), datetime.now().timestamp())
    )


async def create(user_id: int, invoice_number: str) -> None:
    user_invoice[user_id] = invoice_number
    invoice_photo_count.setdefault(invoice_number, 0)
    invoice_video_count.setdefault(invoice_number, 0)
    invoice_document_count.setdefault(invoice_number, 0)
    now = datetime.now()
    user_last_activity[user_id] = now
    await db.upsert_session(user_id, invoice_number, now.timestamp())
    await db.upsert_invoice_files(invoice_number, 0, 0, 0)
    await db.increment_stat('total_invoices')


async def reset(user_id: int) -> tuple[bool, str, int, int, int]:
    """Returns (was_active, invoice, photo_count, video_count, document_count)."""
    if user_id not in user_invoice:
        return False, "", 0, 0, 0
    invoice = user_invoice.pop(user_id)
    p = invoice_photo_count.pop(invoice, 0)
    v = invoice_video_count.pop(invoice, 0)
    d = invoice_document_count.pop(invoice, 0)
    user_last_activity.pop(user_id, None)
    await db.delete_session(user_id)
    return True, invoice, p, v, d


async def increment_file_count(invoice_number: str, file_type: str) -> int:
    """Increment count for file_type ('photo'|'video'|'document'). Returns new count."""
    if file_type == 'photo':
        invoice_photo_count[invoice_number] = invoice_photo_count.get(invoice_number, 0) + 1
        count = invoice_photo_count[invoice_number]
    elif file_type == 'video':
        invoice_video_count[invoice_number] = invoice_video_count.get(invoice_number, 0) + 1
        count = invoice_video_count[invoice_number]
    else:
        invoice_document_count[invoice_number] = invoice_document_count.get(invoice_number, 0) + 1
        count = invoice_document_count[invoice_number]
    await db.upsert_invoice_files(
        invoice_number,
        invoice_photo_count.get(invoice_number, 0),
        invoice_video_count.get(invoice_number, 0),
        invoice_document_count.get(invoice_number, 0),
    )
    return count


async def start_cleanup_task() -> None:
    """Background task: purge stale in-memory sessions every hour."""
    while True:
        await asyncio.sleep(3600)
        now = datetime.now()
        cutoff_ts = now.timestamp() - INACTIVITY_TIMEOUT_SECONDS
        stale = [uid for uid, ts in user_last_activity.items()
                 if ts.timestamp() < cutoff_ts]
        for uid in stale:
            invoice = user_invoice.pop(uid, None)
            user_last_activity.pop(uid, None)
            if invoice:
                invoice_photo_count.pop(invoice, None)
                invoice_video_count.pop(invoice, None)
                invoice_document_count.pop(invoice, None)
        removed_db = await db.cleanup_stale_sessions(cutoff_ts)
        if stale or removed_db:
            logger.info(f"🧹 Очистка: {len(stale)} сессий из памяти, {removed_db} из БД")
