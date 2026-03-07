"""Random delay generator for anti-detection."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable


import math


def make_delay_func(
    min_ms: int = 1000,
    max_ms: int = 3000,
    distribution: str = "uniform",
) -> Callable[[], float]:
    """Create a callable that returns a random delay in seconds.

    Args:
        min_ms: Minimum delay in milliseconds.
        max_ms: Maximum delay in milliseconds.
        distribution: One of "uniform", "gaussian", "poisson", "lognormal".

    Returns:
        A callable that returns a random delay in seconds each time it's called.
    """
    min_s = min_ms / 1000.0
    max_s = max_ms / 1000.0
    midpoint = (min_s + max_s) / 2.0
    range_s = max_s - min_s

    def _clamp(value: float) -> float:
        return max(min_s, min(max_s, value))

    if distribution == "gaussian":
        def _delay() -> float:
            return _clamp(random.gauss(midpoint, range_s / 4.0))
    elif distribution == "poisson":
        def _delay() -> float:
            return _clamp(random.expovariate(1.0 / midpoint))
    elif distribution == "lognormal":
        def _delay() -> float:
            return _clamp(random.lognormvariate(math.log(midpoint), 0.5))
    else:
        def _delay() -> float:
            return random.uniform(min_s, max_s)

    return _delay


async def async_delay(delay_func: Callable[[], float] | None) -> None:
    """Await a random delay if a delay function is provided."""
    if delay_func is not None:
        await asyncio.sleep(delay_func())
