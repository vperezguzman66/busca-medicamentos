import re
import httpx
from bs4 import BeautifulSoup
from .base import BaseScraper, Product, resolve_discount

_SEARCH_URL = "https://www.farmaciasahumada.cl/search"
_BASE_URL = "https://www.farmaciasahumada.cl"


def _extract_prices(tile) -> tuple[float | None, str, float | None, str | None]:
    # The current/promotional price only ever appears as plain "$X.XXX" text
    # inside span.sales — there is no clean numeric attribute for it. Some
    # tiles also render a "-XX%" discount badge in the same span, so match
    # just the "$..." amount instead of stripping digits from the whole text
    # (which would concatenate the badge's digits into the price).
    price_val = None
    sales = tile.select_one("span.sales")
    if sales:
        match = re.search(r"\$\s*([\d.,]+)", sales.get_text())
        if match:
            price_val = re.sub(r"[^\d]", "", match.group(1)) or None

    # The pre-discount ("Precio normal") price, when present, does carry a
    # clean numeric attribute on the struck-through <del> element.
    original_val = None
    del_value = tile.select_one("del span.value")
    if del_value:
        original_val = del_value.get("content")

    return resolve_discount(price_val, original_val)


class AhumadaScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {**self.HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    _SEARCH_URL,
                    params={"q": query},
                    headers=headers,
                )
                resp.raise_for_status()
                html = resp.text
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        tiles = soup.select("div.product-tile-wrapper[data-pid]")

        products = []
        for tile in tiles[:max_results]:
            try:
                pid = tile.get("data-pid")
                link = tile.select_one(".pdp-link a")
                if not link:
                    continue
                name = link.get_text(strip=True)
                href = link.get("href", "")
                url = href if href.startswith("http") else f"{_BASE_URL}{href}"

                price, price_text, original_price, original_price_text = _extract_prices(tile)

                img = tile.select_one('img[itemprop="image"]') or tile.select_one("img")
                image = img.get("src") or img.get("data-src") if img else None

                products.append(
                    Product(
                        name=name,
                        price=price,
                        price_text=price_text,
                        url=url,
                        image=image,
                        store="Farmacias Ahumada",
                        store_id="ahumada",
                        sku=pid,
                        original_price=original_price,
                        original_price_text=original_price_text,
                    )
                )
            except (KeyError, TypeError):
                continue

        return products
