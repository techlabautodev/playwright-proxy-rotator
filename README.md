# playwright-proxy-rotator

A Python helper that binds each Playwright browser context to a different HTTP proxy from a pool, with sticky IP per session.

**For whom:** engineers automating anti-bot-sensitive flows (signup, scraping, captcha-heavy forms) who need a different residential IP per browser session without re-writing browser launches.

**Install (copyable):**

```bash
pip install playwright && playwright install chromium
```

## Minimal example

```python
import asyncio
from rotator import ProxyPool, launch_context

proxies = ["http://user:pass@res-1.example:9000",
           "http://user:pass@res-2.example:9000"]
pool = ProxyPool(proxies)

async def main():
    async with launch_context(pool.next()) as (page, ctx):
        await page.goto("https://api.ipify.org")
        print(await page.inner_text("body"))  # your proxy's IP

asyncio.run(main())
```

## Why

Datacenter IPs get flagged by anti-bot providers before your request is ever read — IP reputation is the first gate, not the captcha. A rotating pool fixes the wrong problem if every new page shares one IP: sticky-per-session rotation keeps a single identity coherent for a full browser session (cookies, fingerprints, session state) while giving the *next* session a clean slate.

This is the smallest piece of a larger automation pipeline — it only manages proxy selection and context creation. Fingerprinting, captcha solving, and pacing live elsewhere.

## What works / what doesn't

- Works: round-robin selection, sticky IP per context, retry on proxy connect failure, config from JSON or env.
- Doesn't (yet): dead-proxy eviction with health checks, HTTP/2 vs HTTP/1.1 per-proxy selection, SOCKS5 auth beyond username/password.

## License

MIT — see `LICENSE`. Contributions welcome, see `CONTRIBUTING.md`.
