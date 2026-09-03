"""Simple async-friendly rate limiter / delay helper."""

import asyncio
import time
from collections import deque
from typing import Optional

from app.config import get_settings


class RateLimiter:
    """Token-bucket style limiter with minimum delay between requests."""

    def __init__(
        self,
        delay: Optional[float] = None,
        max_concurrent: Optional[int] = None,
    ):
        settings = get_settings()
        self.delay = delay if delay is not None else settings.crawl_delay
        self.max_concurrent = (
            max_concurrent
            if max_concurrent is not None
            else settings.max_concurrent_requests
        )
        self._last_request = 0.0
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)
            self._last_request = time.monotonic()

    def release(self) -> None:
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
