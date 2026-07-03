import httpx
from .base import BaseScraper, Product, format_clp_price

_SEARCH_URL = "https://farmaciasdeldrsimicl.vtexcommercestable.com.br/api/catalog_system/pub/products/search"
_BASE_URL = "https://www.drsimi.cl"


class DrSimiScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {**self.HEADERS, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _SEARCH_URL,
                    params={"ft": query, "_from": 0, "_to": max(max_results - 1, 0)},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        products = []
        for p in data[:max_results]:
            try:
                item = p["items"][0]
                seller = item["sellers"][0]["commertialOffer"]
                # Prefer the seller's active Price; fall back to ListPrice if unavailable
                price_val = seller.get("Price") or seller.get("ListPrice")
                price, price_text = format_clp_price(price_val)

                link_text = p.get("linkText", "")
                image = (item.get("images") or [{}])[0].get("imageUrl")

                products.append(
                    Product(
                        name=p["productName"],
                        price=price,
                        price_text=price_text,
                        url=f"{_BASE_URL}/{link_text}/p" if link_text else _BASE_URL,
                        image=image,
                        store="Doctor Simi",
                        store_id="drsimi",
                        sku=item.get("itemId"),
                    )
                )
            except (KeyError, IndexError, TypeError):
                continue

        return products
