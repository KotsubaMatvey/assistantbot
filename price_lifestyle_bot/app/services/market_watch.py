from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class MarketAsset:
    key: str
    name: str
    yahoo_symbol: str


@dataclass(frozen=True)
class MarketQuote:
    key: str
    name: str
    value: Decimal | None
    unit: str
    source: str
    change: Decimal | None = None
    change_percent: Decimal | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None and self.error is None


@dataclass(frozen=True)
class MarketWatchResult:
    quotes: list[MarketQuote]
    fetched_at: datetime


DEFAULT_YAHOO_ASSETS: tuple[MarketAsset, ...] = (
    MarketAsset("btc", "Bitcoin", "BTC-USD"),
    MarketAsset("spx", "S&P 500", "^GSPC"),
    MarketAsset("nasdaq", "Nasdaq Composite", "^IXIC"),
    MarketAsset("dow", "Dow Jones", "^DJI"),
)


async def fetch_market_watch() -> MarketWatchResult:
    timeout = httpx.Timeout(10.0)
    headers = {"User-Agent": "assistantbot/0.1"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        quote_tasks = [_fetch_yahoo_quote(client, asset) for asset in DEFAULT_YAHOO_ASSETS]
        quote_tasks.append(_fetch_btc_dominance(client))
        quotes = await asyncio.gather(*quote_tasks)
    return MarketWatchResult(quotes=list(quotes), fetched_at=datetime.now(UTC))


def format_market_watch(result: MarketWatchResult) -> str:
    lines = [
        "Рынки",
        f"Обновлено: {result.fetched_at:%Y-%m-%d %H:%M} UTC",
        "",
    ]
    for quote_item in result.quotes:
        if not quote_item.ok:
            lines.append(f"{quote_item.name}: нет данных ({quote_item.error or 'ошибка'})")
            continue
        value = _format_decimal(quote_item.value)
        change = _format_change(quote_item.change, quote_item.change_percent)
        lines.append(f"{quote_item.name}: {value}{quote_item.unit}{change}")
    lines.append("")
    lines.append(
        "Данные публичных источников могут задерживаться и не являются торговой рекомендацией."
    )
    return "\n".join(lines)


def market_watch_memory_note(result: MarketWatchResult) -> str:
    return "# Market watch\n\n" + format_market_watch(result)


async def _fetch_yahoo_quote(client: httpx.AsyncClient, asset: MarketAsset) -> MarketQuote:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(asset.yahoo_symbol, safe='')}?range=5d&interval=1d"
    )
    try:
        response = await client.get(url)
        response.raise_for_status()
        return parse_yahoo_quote(asset=asset, payload=response.json())
    except Exception as exc:
        return MarketQuote(
            key=asset.key,
            name=asset.name,
            value=None,
            unit="",
            source="Yahoo Finance",
            error=str(exc)[:160],
        )


def parse_yahoo_quote(*, asset: MarketAsset, payload: dict[str, Any]) -> MarketQuote:
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise ValueError("Yahoo response has no chart result")
    meta = result.get("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("Yahoo response has no metadata")
    price = _decimal_or_none(meta.get("regularMarketPrice"))
    previous = _decimal_or_none(meta.get("previousClose")) or _decimal_or_none(
        meta.get("chartPreviousClose")
    )
    if price is None:
        raise ValueError("Yahoo response has no price")
    change = price - previous if previous is not None else None
    change_percent = (
        (change / previous * Decimal("100")) if change is not None and previous else None
    )
    return MarketQuote(
        key=asset.key,
        name=asset.name,
        value=price,
        unit=" USD" if asset.key == "btc" else " pt",
        source="Yahoo Finance",
        change=change,
        change_percent=change_percent,
    )


async def _fetch_btc_dominance(client: httpx.AsyncClient) -> MarketQuote:
    try:
        response = await client.get("https://api.coingecko.com/api/v3/global")
        response.raise_for_status()
        raw = response.json()
        value = _decimal_or_none(
            raw.get("data", {}).get("market_cap_percentage", {}).get("btc")
        )
        if value is None:
            raise ValueError("CoinGecko response has no BTC dominance")
        return MarketQuote(
            key="btc.d",
            name="BTC Dominance",
            value=value,
            unit="%",
            source="CoinGecko",
        )
    except Exception as exc:
        return MarketQuote(
            key="btc.d",
            name="BTC Dominance",
            value=None,
            unit="%",
            source="CoinGecko",
            error=str(exc)[:160],
        )


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= Decimal("100"):
        return f"{value.quantize(Decimal('0.01'))}"
    return f"{value.quantize(Decimal('0.001'))}"


def _format_change(change: Decimal | None, change_percent: Decimal | None) -> str:
    if change is None or change_percent is None:
        return ""
    sign = "+" if change >= 0 else ""
    return f" ({sign}{_format_decimal(change)}, {sign}{change_percent.quantize(Decimal('0.01'))}%)"
