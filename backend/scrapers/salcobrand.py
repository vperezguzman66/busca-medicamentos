import httpx
from .base import BaseScraper, Product, format_clp_price

_ALGOLIA_URL = "https://GM3RP06HJG-dsn.algolia.net/1/indexes/sb_variant_production/query"
_ALGOLIA_APP_ID = "GM3RP06HJG"
_ALGOLIA_API_KEY = "0259fe250b3be4b1326eb85e47aa7d81"
_BASE_URL = "https://salcobrand.cl"


class SalcoBrandScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {
            "X-Algolia-API-Key": _ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
            "Referer": f"{_BASE_URL}/",
            "Content-Type": "application/json",
        }
        params = f"query={query}&hitsPerPage={max_results}"
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
                price, price_text = format_clp_price(price_val)

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
                    )
                )
            except (KeyError, TypeError):
                continue

        return products
