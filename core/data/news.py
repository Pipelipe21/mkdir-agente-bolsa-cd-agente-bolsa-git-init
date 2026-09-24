"""Titulares recientes por activo vía yfinance (sirve para acciones y cripto)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from core.models import Asset, AssetType


@dataclass(frozen=True)
class Headline:
    title: str
    publisher: str = ""
    summary: str = ""
    published: datetime | None = None


def news_symbol(asset: Asset) -> str:
    """yfinance usa 'BTC-USD' para cripto; 'BTC/USDT' → 'BTC-USD'."""
    if asset.type is AssetType.CRYPTO:
        return asset.symbol.split("/")[0] + "-USD"
    return asset.symbol


def _parse_date(value) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def parse_news(items: list[dict]) -> list[Headline]:
    """Acepta el formato nuevo de yfinance (con 'content') y el antiguo (plano)."""
    headlines = []
    for item in items:
        content = item.get("content", item)
        title = (content.get("title") or "").strip()
        if not title:
            continue
        provider = content.get("provider") or {}
        headlines.append(
            Headline(
                title=title,
                publisher=provider.get("displayName") or content.get("publisher") or "",
                summary=(content.get("summary") or "").strip(),
                published=_parse_date(content.get("pubDate") or content.get("providerPublishTime")),
            )
        )
    return headlines


def fetch_headlines(asset: Asset, count: int = 8) -> list[Headline]:
    import yfinance as yf

    return parse_news(yf.Ticker(news_symbol(asset)).get_news(count=count))[:count]
