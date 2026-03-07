"""Proxy pool: load, rotate, cycle with metadata support."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProxyEntry:
    """A proxy with optional metadata."""

    url: str
    proxy_type: str = "datacenter"  # "residential" | "datacenter" | "mobile"
    country: str | None = None
    city: str | None = None


def _parse_proxy_line(line: str) -> ProxyEntry:
    """Parse a proxy line: 'url' or 'url|type|country' or 'url|type|country|city'."""
    parts = line.split("|")
    url = parts[0].strip()
    proxy_type = parts[1].strip() if len(parts) > 1 else "datacenter"
    country = parts[2].strip() if len(parts) > 2 else None
    city = parts[3].strip() if len(parts) > 3 else None
    return ProxyEntry(url=url, proxy_type=proxy_type, country=country, city=city)


class ProxyPool:
    """Rotating proxy pool with metadata-based filtering."""

    def __init__(self, proxies: list[ProxyEntry] | None = None) -> None:
        self._proxies: list[ProxyEntry] = list(proxies) if proxies else []
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
            proxy_file: Path to a file with one proxy URL per line,
                        or 'url|type|country' pipe-delimited format.
        """
        entries: list[ProxyEntry] = []
        if proxy:
            entries.append(ProxyEntry(url=proxy))
        if proxy_file:
            path = Path(proxy_file)
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    entries.append(_parse_proxy_line(line))
        return cls(entries)

    @property
    def count(self) -> int:
        return len(self._proxies)

    @property
    def is_empty(self) -> bool:
        return not self._proxies

    def next(self) -> ProxyEntry | None:
        """Return the next proxy in rotation, or None if pool is empty."""
        if self._cycle is None:
            return None
        return next(self._cycle)

    def next_by_type(self, proxy_type: str) -> ProxyEntry | None:
        """Return the next proxy matching the given type, or None."""
        for entry in self._proxies:
            if entry.proxy_type == proxy_type:
                return entry
        return None

    def next_by_country(self, country: str) -> ProxyEntry | None:
        """Return the next proxy matching the given country code, or None."""
        country_upper = country.upper()
        for entry in self._proxies:
            if entry.country and entry.country.upper() == country_upper:
                return entry
        return None
