"""Random delay generator."""

from __future__ import annotations

import asyncio
import random
from typing import Callable


def make_delay_fn(min_ms: int = 1000, max_ms: int = 3000) -> Callable[[], float]:
    """Return a callable that produces a random delay in *seconds* (uniform).

    Each call returns a new random value between *min_ms* and *max_ms*
    (converted to seconds).
    """
    min_s = min_ms / 1000.0
    max_s = max_ms / 1000.0

    def _delay() -> float:
        return random.uniform(min_s, max_s)

    return _delay


async def async_delay(delay_fn: Callable[[], float]) -> None:
    """Await a delay produced by *delay_fn*."""
    await asyncio.sleep(delay_fn())
