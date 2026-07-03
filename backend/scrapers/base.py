from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Product:
    name: str
    price: float | None
    price_text: str
    url: str
    image: str | None
    store: str
    store_id: str
    sku: str | None = None
    original_price: float | None = None
    original_price_text: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "price": self.price,
            "price_text": self.price_text,
            "url": self.url,
            "image": self.image,
            "store": self.store,
            "store_id": self.store_id,
            "sku": self.sku,
            "original_price": self.original_price,
            "original_price_text": self.original_price_text,
        }


def format_clp_price(value) -> tuple[float | None, str]:
    if not value:
        return None, "Sin precio"
    try:
        price = float(value)
        return price, f"${int(price):,}".replace(",", ".")
    except (ValueError, TypeError):
        return None, "Sin precio"


def resolve_discount(price_val, original_val) -> tuple[float | None, str, float | None, str | None]:
    """Pairs a current price with its pre-discount price, dropping the
    original when it isn't actually higher (bad data, or no real promo)."""
    price, price_text = format_clp_price(price_val)
    original_price, original_price_text = format_clp_price(original_val)
    if original_price is None or price is None or original_price <= price:
        original_price, original_price_text = None, None
    return price, price_text, original_price, original_price_text


class BaseScraper(ABC):
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-CL,es;q=0.9",
        "Accept": "application/json, text/html, */*",
    }

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        pass
