#!/usr/bin/env python3
"""
proxypool.py — Thread-safe rotating proxy pool.

Reads proxies from a text file (one per line, format: proto://user:pass@host:port)
and returns them in round-robin or random order. Thread-safe.

Usage:
    from qoder_autopilot.utils.proxypool import ProxyPool

    pool = ProxyPool("proxy.txt")
    proxy = pool.get()        # {"http": "...", "https": "..."}
    proxy = pool.random()     # Random pick instead of round-robin
    pool.reload()             # Re-read proxy.txt at runtime
"""

import os
import random
import threading
from typing import Optional

__all__ = ["ProxyPool"]


class ProxyPool:
    """Thread-safe rotating proxy pool loaded from a text file."""

    def __init__(self, path: str | None = None, auto_reload: bool = True):
        """
        Args:
            path: Path to proxy file. Defaults to PROXY_POOL_PATH env var or
                  'proxy.txt' in the working directory.
            auto_reload: Re-read the file on every get() call so you can
                         hot-edit proxy.txt while the script runs.
        """
        self.path = path or os.getenv("PROXY_POOL_PATH", "proxy.txt")
        self.auto_reload = auto_reload
        self._lock = threading.Lock()
        self._proxies: list[str] = []
        self._index = 0
        self._load()

    def _load(self) -> None:
        """Read proxies from file. Expects one proxy URL per line.
        Lines starting with # or empty lines are skipped."""
        self._proxies.clear()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._proxies.append(line)
        except FileNotFoundError:
            # File doesn't exist yet — empty pool till it does
            pass

    @property
    def count(self) -> int:
        """Number of proxies currently loaded."""
        return len(self._proxies)

    def get(self) -> dict[str, str] | None:
        """Return the next proxy in round-robin, or None if pool is empty.

        Returns a dict suitable for passing to requests.Session.proxies:
            {"http": "http://user:pass@host:port",
             "https": "http://user:pass@host:port"}
        """
        with self._lock:
            if self.auto_reload:
                self._load()
            if not self._proxies:
                return None
            url = self._proxies[self._index % len(self._proxies)]
            self._index += 1
        return {"http": url, "https": url}

    def random(self) -> dict[str, str] | None:
        """Return a random proxy from the pool, or None if empty."""
        with self._lock:
            if self.auto_reload:
                self._load()
            if not self._proxies:
                return None
            url = random.choice(self._proxies)
        return {"http": url, "https": url}

    def reload(self) -> int:
        """Force re-read proxy.txt. Returns the number of proxies loaded."""
        with self._lock:
            self._load()
        return self.count

    def __len__(self) -> int:
        return self.count

    def __bool__(self) -> bool:
        return self.count > 0
