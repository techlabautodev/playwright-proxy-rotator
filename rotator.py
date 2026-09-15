"""Sticky per-session proxy rotation for Playwright.

One browser context = one proxy from the pool. The next context gets the next
proxy. Rotation happens across sessions, not across pages, so a single session
keeps one coherent network identity (cookies, TLS fingerprint, IP).

Usage:
    pool = ProxyPool(["http://user:pass@res-1.example:9000", ...])
    async with launch_context(pool.next()) as (page, ctx):
        ...
"""

import itertools
import json
import os

from playwright.async_api import async_playwright


class ProxyPool:
    """Round-robin proxy pool with optional retry on connect failure."""

    def __init__(self, proxies, retries=2):
        if not proxies:
            raise ValueError("proxies must be a non-empty list")
        self._proxies = list(proxies)
        self._cycle = itertools.cycle(self._proxies)
        self.retries = retries

    def next(self):
        return next(self._cycle)

    @classmethod
    def from_file(cls, path):
        """Load proxies from JSON: either a list of strings or {"proxies": [...]}."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        proxies = data["proxies"] if isinstance(data, dict) else data
        return cls(proxies)

    @classmethod
    def from_env(cls, var="PROXY_POOL"):
        """Comma-separated proxy list from an environment variable."""
        raw = os.environ.get(var, "")
        proxies = [p.strip() for p in raw.split(",") if p.strip()]
        return cls(proxies)


class _ContextGuard:
    """Async context manager yielding (page, context) and closing both on exit."""

    def __init__(self, browser, proxy):
        self.browser = browser
        self.proxy = proxy
        self._context = None

    async def __aenter__(self):
        self._context = await self.browser.new_context(proxy={"server": self.proxy})
        page = await self._context.new_page()
        return page, self._context

    async def __aexit__(self, *exc):
        await self._context.close()


class launch_context:
    """Launch Chromium and open one proxied context.

    Retries a bounded number of times on proxy connect errors before giving up,
    so a single dead proxy doesn't kill the whole run.
    """

    def __init__(self, proxy, retries=2):
        self.proxy = proxy
        self.retries = retries
        self._playwright = None
        self._browser = None
        self._guard = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        last = None
        for attempt in range(self.retries + 1):
            guard = _ContextGuard(self._browser, self.proxy)
            try:
                page, ctx = await guard.__aenter__()
                self._guard = guard
                return page, ctx
            except Exception as e:  # pragma: no cover - proxy/network error
                last = e
                await guard.__aexit__(None, None, None)
        raise RuntimeError(f"proxy connect failed after {self.retries} retries: {last}")

    async def __aexit__(self, *exc):
        if self._guard is not None:
            await self._guard.__aexit__(*exc)
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
