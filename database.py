import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id INTEGER PRIMARY KEY,
                invoice_number TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invoice_files (
                invoice_number TEXT PRIMARY KEY,
                photo_count INTEGER DEFAULT 0,
                video_count INTEGER DEFAULT 0,
                document_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_name TEXT,
                uploaded_at REAL NOT NULL,
                UNIQUE(invoice_number, file_hash)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        for key in ('total_photos', 'total_videos', 'total_documents', 'total_invoices', 'errors'):
            await db.execute(
                "INSERT OR IGNORE INTO bot_stats (key, value) VALUES (?, 0)", (key,)
            )
        await db.commit()


async def load_all_sessions() -> list[tuple]:
    """Returns [(user_id, invoice_number, updated_at), ...]"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, invoice_number, updated_at FROM sessions") as cur:
            return await cur.fetchall()


async def upsert_session(user_id: int, invoice_number: str, updated_at: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO sessions (user_id, invoice_number, updated_at) VALUES (?, ?, ?)",
            (user_id, invoice_number, updated_at)
        )
        await db.commit()


async def delete_session(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await db.commit()


async def cleanup_stale_sessions(cutoff_ts: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff_ts,))
        await db.commit()
        return cur.rowcount


async def get_invoice_files(invoice_number: str) -> tuple[int, int, int]:
    """Returns (photo_count, video_count, document_count)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT photo_count, video_count, document_count FROM invoice_files WHERE invoice_number = ?",
            (invoice_number,)
        ) as cur:
            row = await cur.fetchone()
            return row if row else (0, 0, 0)


async def upsert_invoice_files(invoice_number: str, photo_count: int, video_count: int, document_count: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO invoice_files (invoice_number, photo_count, video_count, document_count) VALUES (?, ?, ?, ?)",
            (invoice_number, photo_count, video_count, document_count)
        )
        await db.commit()


async def is_duplicate(invoice_number: str, file_hash: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM file_hashes WHERE invoice_number = ? AND file_hash = ?",
            (invoice_number, file_hash)
        ) as cur:
            return await cur.fetchone() is not None


async def add_file_hash(invoice_number: str, file_hash: str, file_name: str, uploaded_at: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO file_hashes (invoice_number, file_hash, file_name, uploaded_at) VALUES (?, ?, ?, ?)",
            (invoice_number, file_hash, file_name, uploaded_at)
        )
        await db.commit()


async def get_stat(key: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_stats WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_stat(key: str, delta: int = 1) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (key, delta, delta)
        )
        await db.commit()


async def get_all_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM bot_stats") as cur:
            rows = await cur.fetchall()
            return {k: v for k, v in rows}
