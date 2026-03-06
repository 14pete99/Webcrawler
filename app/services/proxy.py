"""Proxy pool: load, rotate, cycle."""

from __future__ import annotations

import itertools
from pathlib import Path


class ProxyPool:
    """Thread-safe rotating proxy pool."""

    def __init__(self, proxies: list[str] | None = None) -> None:
        self._proxies: list[str] = list(proxies) if proxies else []
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    @classmethod
    def from_args(
        cls,
        proxy: str | None = None,
        proxy_file: str | None = None,
    ) -> ProxyPool:
        """Build a ProxyPool from CLI-style arguments.

        Args:
            proxy: Single proxy URL.
            proxy_file: Path to a file with one proxy URL per line.
        """
        proxies: list[str] = []
        if proxy:
            proxies.append(proxy)
        if proxy_file:
            path = Path(proxy_file)
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append(line)
        return cls(proxies)

    @property
    def count(self) -> int:
        return len(self._proxies)

    @property
    def is_empty(self) -> bool:
        return not self._proxies

    def next(self) -> str | None:
        """Return the next proxy in rotation, or None if pool is empty."""
        if self._cycle is None:
            return None
        return next(self._cycle)
