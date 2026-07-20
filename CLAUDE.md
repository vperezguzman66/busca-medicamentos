# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BuscaMedicamentos compares medication prices across four Chilean pharmacy chains — SalcoBrand, Cruz Verde, Farmacias Ahumada, and Doctor Simi — by scraping each one's public search in parallel and merging the results. It's a comparator only: no purchases, prescriptions, or patient data.

## Commands

```bash
./run.sh                 # creates .venv, installs deps + Playwright's Chromium, runs uvicorn --reload on :8000
```

Manual equivalent, from `backend/`:

```bash
source ../.venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

There is no test suite, linter, or frontend build step in this repo. The frontend (`frontend/`) is plain HTML/CSS/JS served directly by FastAPI's `StaticFiles` — no bundler, no npm.

## Architecture

**One shared Chromium instance.** Cruz Verde has no scrapeable API (it sits behind Incapsula/WAF and its API requires an OAuth session), so it's the only scraper that drives a real browser via Playwright. A single `browser` instance is launched once in FastAPI's `lifespan` (`backend/main.py`) and injected into `CruzVerdeScraper`; each search opens a lightweight `browser.new_context()` rather than a new browser process. Don't launch a browser per-request.

**Streaming instead of waiting for the slowest store.** Cruz Verde's full-page render is several seconds slower than the other three scrapers. `/api/search` is a Server-Sent Events endpoint (`_do_search_stream` in `main.py`): as each store's `asyncio.as_completed` task finishes, it yields a growing snapshot (`results` sorted so far + `pending` list of stores still running), instead of blocking on `asyncio.gather` until everyone is done. `/api/search-batch` (CSV upload) is also SSE, one event per medication in the batch, bounded by `asyncio.Semaphore(3)` concurrent lookups. When touching search logic, preserve this incremental-yield structure rather than collapsing it back to a single blocking response.

**Scraper contract.** Every scraper in `backend/scrapers/` subclasses `BaseScraper` (`base.py`) and implements `async def search(query, max_results) -> list[Product]`. `Product` is a plain dataclass with `to_dict()`. Shared helpers in `base.py`:
- `format_clp_price(value)` — parses a raw price into `(float, "$X.XXX")` formatted for Chilean pesos.
- `resolve_discount(price_val, original_val)` — pairs current + pre-discount price, dropping the "original" if it isn't actually higher than the current price (guards against bad source data being read as a fake promo).

Per-store quirks that aren't obvious from the code alone (each site uses a completely different backend, so there's no shared scraping strategy):
- **SalcoBrand** (`salcobrand.py`): queries Algolia directly (`POST https://GM3RP06HJG-dsn.algolia.net/...`) with a `Referer: https://salcobrand.cl/` header, using the same public read-only key the site's own frontend bundle uses — not a project secret. Price is `direct_discount` if present, else `normal_price`. Also handles combined-dose queries like "colmibe 40/10".
- **Farmacias Ahumada** (`ahumada.py`): server-rendered HTML (Salesforce Commerce Cloud / Demandware), parsed with BeautifulSoup. The current price has no clean attribute — it must be scraped as text from `span.sales`; only the crossed-out list price has a clean `content` attribute (inside `<del>`).
- **Doctor Simi** (`drsimi.py`): VTEX legacy catalog API on `www.drsimi.cl` (careful: `farmaciasdrsimi.cl` does not resolve). The `?ft=` search endpoint silently returns zero/blocked results for any query of 2+ words — this was a real bug, not a hypothetical, so don't reintroduce naive multi-word `ft=` queries without checking how the current code works around it.
- **Cruz Verde** (`cruzverde.py`): Playwright only, see above. Price is read from `p.text-green-turquoise` in the rendered DOM.

**Failure isolation.** In both `_do_search` and `_do_search_stream`, each store's task result is checked with `isinstance(result, Exception)` and pushed to an `errors` list rather than failing the whole request — one pharmacy's scraper breaking (site redesign, WAF change) must never take down results from the other three.

**In-memory cache.** `_cache` in `main.py` is a simple dict keyed by `(query.lower().strip(), tuple(sorted(stores)), max_results)` with a 5-minute TTL and a crude eviction (drops the 50 oldest entries once above 200). No external cache/DB is involved.

**Security posture** (see also README "Seguridad"): `slowapi` rate limiting (20/min on `/api/search`, 5/min on `/api/search-batch`, 60/min default), CSP + security headers via `SecurityHeadersMiddleware`, CORS locked to `localhost:8000`/`127.0.0.1:8000`, 100 KB cap on uploaded CSVs. Keep these in mind when changing endpoints — don't loosen CORS or rate limits without a reason.
