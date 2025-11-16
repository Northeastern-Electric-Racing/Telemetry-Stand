from collections import deque
import asyncio


async def get_latest_value(
    data_store: dict[str, deque], data_lock: asyncio.Lock, key: str
):
    async with data_lock:
        dq = data_store.get(key)
        if dq and len(dq) > 0:
            return dq[-1]
        return None


async def get_latest_n(
    data_store: dict[str, deque], data_lock: asyncio.Lock, key: str, n: int
) -> list:
    """Return up to the last n values for key as a list (oldest..newest)."""
    async with data_lock:
        dq = data_store.get(key)
        if not dq:
            return []
        # slice the deque safely
        return list(dq)[-n:]
