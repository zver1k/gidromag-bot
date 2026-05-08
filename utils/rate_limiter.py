import asyncio
from collections import defaultdict

# 20 uploads per 60 seconds per user
_MAX_REQUESTS = 20
_WINDOW_SECONDS = 60

_timestamps: dict[int, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


async def check(user_id: int) -> tuple[bool, int]:
    """Returns (allowed, wait_seconds). Registers the request if allowed."""
    import time
    async with _lock:
        now = time.monotonic()
        cutoff = now - _WINDOW_SECONDS
        _timestamps[user_id] = [t for t in _timestamps[user_id] if t > cutoff]
        if len(_timestamps[user_id]) >= _MAX_REQUESTS:
            wait = int(_WINDOW_SECONDS - (now - _timestamps[user_id][0])) + 1
            return False, wait
        _timestamps[user_id].append(now)
        return True, 0
