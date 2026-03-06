"""Proxy pool: load, rotate, cycle."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterator


class ProxyPool:
    """An iterable pool of proxy URLs that cycles infinitely."""

    def __init__(self, proxies: list[str] | None = None) -> None:
        self._proxies: list[str] = list(proxies) if proxies else []
        self._cycle: Iterator[str] | None = None
        if self._proxies:
            self._cycle = itertools.cycle(self._proxies)

    @classmethod
    def from_args(cls, proxy: str | None = None, proxy_file: str | None = None) -> "ProxyPool":
        """Build a pool from CLI-style arguments."""
        proxies: list[str] = []
        if proxy:
            proxies.append(proxy)
        if proxy_file:
            path = Path(proxy_file)
            if path.is_file():
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        proxies.append(line)
        return cls(proxies)

    def __len__(self) -> int:
        return len(self._proxies)

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def next(self) -> str | None:
        """Return the next proxy URL, or ``None`` if the pool is empty."""
        if self._cycle is None:
            return None
        return next(self._cycle)
