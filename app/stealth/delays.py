"""Random delay generator for anti-detection."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable


def make_delay_func(min_ms: int = 1000, max_ms: int = 3000) -> Callable[[], float]:
    """Create a callable that returns a random delay in seconds.

    Uses uniform distribution between min_ms and max_ms.

    Args:
        min_ms: Minimum delay in milliseconds.
        max_ms: Maximum delay in milliseconds.

    Returns:
        A callable that returns a random delay in seconds each time it's called.
    """
    min_s = min_ms / 1000.0
    max_s = max_ms / 1000.0

    def _delay() -> float:
        return random.uniform(min_s, max_s)

    return _delay


async def async_delay(delay_func: Callable[[], float] | None) -> None:
    """Await a random delay if a delay function is provided."""
    if delay_func is not None:
        await asyncio.sleep(delay_func())
