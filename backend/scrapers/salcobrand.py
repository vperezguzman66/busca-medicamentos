import re
import httpx
from urllib.parse import quote
from .base import BaseScraper, Product, resolve_discount

_ALGOLIA_URL = "https://GM3RP06HJG-dsn.algolia.net/1/indexes/sb_variant_production/query"
_ALGOLIA_APP_ID = "GM3RP06HJG"
_ALGOLIA_API_KEY = "0259fe250b3be4b1326eb85e47aa7d81"
_BASE_URL = "https://salcobrand.cl"

# Algolia's analyzer returns 0 hits for any query containing "/", so combo
# dosages written as "40/10" (common for medications) never match anything.
# Rewriting each side as its own "mg" token ("40mg 10mg") searches correctly.
_DOSE_SLASH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:mg)?\s*/\s*(\d+(?:\.\d+)?)\s*(?:mg)?", re.IGNORECASE)


def _normalize_query(query: str) -> str:
    return _DOSE_SLASH_RE.sub(r"\1mg \2mg", query)


class SalcoBrandScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {
            "X-Algolia-API-Key": _ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
            "Referer": f"{_BASE_URL}/",
            "Content-Type": "application/json",
        }
        params = f"query={quote(_normalize_query(query))}&hitsPerPage={max_results}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _ALGOLIA_URL,
                    json={"params": params},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        products = []
        for hit in data.get("hits", []):
            try:
                # Direct discount (if any) beats the normal price, like Homecenter's priority list
                discount = hit.get("direct_discount")
                price_val = discount if discount else hit.get("normal_price")
                price, price_text, original_price, original_price_text = resolve_discount(
                    price_val, hit.get("normal_price")
                )

                slug = hit.get("slug", "")
                products.append(
                    Product(
                        name=hit["name"],
                        price=price,
                        price_text=price_text,
                        url=f"{_BASE_URL}/products/{slug}" if slug else _BASE_URL,
                        image=hit.get("thumbnail_image_url") or hit.get("catalog_image_url"),
                        store="SalcoBrand",
                        store_id="salcobrand",
                        sku=hit.get("sku") or str(hit.get("id", "")),
                        original_price=original_price,
                        original_price_text=original_price_text,
                    )
                )
            except (KeyError, TypeError):
                continue

        return products
