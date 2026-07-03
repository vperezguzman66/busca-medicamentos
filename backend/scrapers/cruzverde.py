import re
from .base import BaseScraper, Product, format_clp_price

_BASE_URL = "https://www.cruzverde.cl"
_CARD_SELECTOR = (
    "div.max-w-xs.w-full.h-full.border.border-gray-light.bg-white.shadow"
    ".text-center.overflow-hidden"
)
_SEARCH_INPUT_SELECTOR = "input[type=search], input[placeholder*='uscar' i], input[name*='search' i]"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class CruzVerdeNotReadyError(Exception):
    pass


class CruzVerdeScraper(BaseScraper):
    # Incapsula + proprietary session auth block direct httpx calls to the API, so this drives a shared Playwright browser instead (assigned by main.py's lifespan).

    def __init__(self):
        self.browser = None

    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        if self.browser is None:
            raise CruzVerdeNotReadyError("El navegador de Cruz Verde aún no está listo")

        context = await self.browser.new_context(
            user_agent=_USER_AGENT,
            locale="es-CL",
            extra_http_headers={"Accept-Language": "es-CL,es;q=0.9"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        try:
            page = await context.new_page()
            await page.goto(_BASE_URL, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(2000)
            await page.fill(_SEARCH_INPUT_SELECTOR, query, timeout=10_000)
            await page.keyboard.press("Enter")
            try:
                await page.locator(_CARD_SELECTOR).first.wait_for(state="attached", timeout=15_000)
            except Exception:
                pass  # genuinely no results for this query — fall through with an empty card list

            cards = await page.locator(_CARD_SELECTOR).all()
            products = []
            for card in cards[:max_results]:
                try:
                    products.append(await self._parse_card(card))
                except Exception:
                    continue
            return [p for p in products if p is not None]
        finally:
            await context.close()

    async def _parse_card(self, card) -> Product | None:
        name_el = card.locator("h2").first
        if await name_el.count() == 0:
            return None
        name = (await name_el.text_content() or "").strip()
        if not name:
            return None

        link_el = card.locator("a[href]").first
        href = await link_el.get_attribute("href") if await link_el.count() > 0 else None
        url = f"{_BASE_URL}{href}" if href and not href.startswith("http") else (href or _BASE_URL)

        img_el = card.locator("img").first
        image = await img_el.get_attribute("src") if await img_el.count() > 0 else None

        sale_el = card.locator("p.text-green-turquoise").first
        price_val = None
        if await sale_el.count() > 0:
            digits = re.sub(r"[^\d]", "", (await sale_el.text_content()) or "")
            price_val = digits or None
        price, price_text = format_clp_price(price_val)

        sku_match = re.search(r"/(\d+)\.html", href or "")
        sku = sku_match.group(1) if sku_match else None

        return Product(
            name=name,
            price=price,
            price_text=price_text,
            url=url,
            image=image,
            store="Cruz Verde",
            store_id="cruzverde",
            sku=sku,
        )
