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


@dataclass(frozen=True)
class MarketSignal:
    name: str
    status: str
    score: Decimal
    reason: str


@dataclass(frozen=True)
class MarketBrief:
    sentiment_label: str
    sentiment_score: Decimal
    risk_regime: str
    signals: list[MarketSignal]
    transmission_chain: list[str]
    data_gaps: list[str]


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


def analyze_market_watch(result: MarketWatchResult) -> MarketBrief:
    sentiment_score = _market_sentiment_score(result.quotes)
    signals = _market_signals(result.quotes)
    risk_regime = _risk_regime(sentiment_score)
    return MarketBrief(
        sentiment_label=_sentiment_label(sentiment_score),
        sentiment_score=sentiment_score,
        risk_regime=risk_regime,
        signals=signals,
        transmission_chain=_transmission_chain(result, risk_regime, sentiment_score),
        data_gaps=[quote.name for quote in result.quotes if not quote.ok],
    )


def format_market_brief(result: MarketWatchResult) -> str:
    brief = analyze_market_watch(result)
    lines = [
        "Market brief",
        f"Updated: {result.fetched_at:%Y-%m-%d %H:%M} UTC",
        "",
        f"Sentiment: {brief.sentiment_label} ({_format_score(brief.sentiment_score)})",
        f"Risk regime: {brief.risk_regime}",
        "",
        "Signal evolution:",
    ]
    lines.extend(
        f"- {signal.name}: {signal.status} ({_format_score(signal.score)}) - {signal.reason}"
        for signal in brief.signals
    )
    lines.extend(["", "Transmission chain:"])
    lines.extend(f"{index}. {item}" for index, item in enumerate(brief.transmission_chain, start=1))
    if brief.data_gaps:
        lines.extend(["", "Data gaps: " + ", ".join(brief.data_gaps)])
    lines.extend(
        [
            "",
            "This is a rules-based market read, not investment advice.",
        ]
    )
    return "\n".join(lines)


def market_brief_memory_note(result: MarketWatchResult) -> str:
    return "# Market analyst brief\n\n" + format_market_brief(result)


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


def _market_sentiment_score(quotes: list[MarketQuote]) -> Decimal:
    weights = {
        "btc": Decimal("0.30"),
        "spx": Decimal("0.25"),
        "nasdaq": Decimal("0.30"),
        "dow": Decimal("0.15"),
    }
    score = Decimal("0")
    weight_total = Decimal("0")
    for key, weight in weights.items():
        quote_item = _quote_by_key(quotes, key)
        if quote_item is None or quote_item.change_percent is None:
            continue
        component = _clamp_decimal(
            quote_item.change_percent / Decimal("3"),
            Decimal("-1"),
            Decimal("1"),
        )
        score += component * weight
        weight_total += weight
    if weight_total:
        score = score / weight_total

    btc_dominance = _quote_by_key(quotes, "btc.d")
    if btc_dominance is not None and btc_dominance.value is not None:
        if btc_dominance.value >= Decimal("55"):
            score -= Decimal("0.08")
        elif btc_dominance.value <= Decimal("50"):
            score += Decimal("0.05")
    return _clamp_decimal(score, Decimal("-1"), Decimal("1")).quantize(Decimal("0.01"))


def _market_signals(quotes: list[MarketQuote]) -> list[MarketSignal]:
    btc = _quote_by_key(quotes, "btc")
    btc_dominance = _quote_by_key(quotes, "btc.d")
    equity_change = _average_change(quotes, ("spx", "nasdaq", "dow"))
    return [
        _change_signal(
            name="BTC momentum",
            change_percent=btc.change_percent if btc else None,
            positive_threshold=Decimal("2"),
            negative_threshold=Decimal("-2"),
        ),
        _change_signal(
            name="Equity risk appetite",
            change_percent=equity_change,
            positive_threshold=Decimal("1"),
            negative_threshold=Decimal("-1"),
        ),
        _dominance_signal(btc_dominance),
    ]


def _change_signal(
    *,
    name: str,
    change_percent: Decimal | None,
    positive_threshold: Decimal,
    negative_threshold: Decimal,
) -> MarketSignal:
    if change_percent is None:
        return MarketSignal(
            name=name,
            status="missing",
            score=Decimal("0"),
            reason="no fresh change data",
        )
    score = _clamp_decimal(change_percent / positive_threshold, Decimal("-1"), Decimal("1"))
    formatted = f"{change_percent.quantize(Decimal('0.01'))}%"
    if change_percent >= positive_threshold:
        return MarketSignal(
            name=name,
            status="strengthened",
            score=score,
            reason=f"move is {formatted}",
        )
    if change_percent <= negative_threshold:
        return MarketSignal(
            name=name,
            status="weakened",
            score=score,
            reason=f"move is {formatted}",
        )
    return MarketSignal(
        name=name,
        status="unchanged",
        score=score,
        reason=f"move is {formatted}",
    )


def _dominance_signal(quote_item: MarketQuote | None) -> MarketSignal:
    if quote_item is None or quote_item.value is None:
        return MarketSignal(
            name="Crypto concentration",
            status="missing",
            score=Decimal("0"),
            reason="BTC dominance unavailable",
        )
    if quote_item.value >= Decimal("55"):
        return MarketSignal(
            name="Crypto concentration",
            status="strengthened",
            score=Decimal("-0.35"),
            reason=f"BTC.D is {_format_decimal(quote_item.value)}%, breadth is narrow",
        )
    if quote_item.value <= Decimal("50"):
        return MarketSignal(
            name="Crypto concentration",
            status="weakened",
            score=Decimal("0.20"),
            reason=f"BTC.D is {_format_decimal(quote_item.value)}%, breadth is wider",
        )
    return MarketSignal(
        name="Crypto concentration",
        status="unchanged",
        score=Decimal("0"),
        reason=f"BTC.D is {_format_decimal(quote_item.value)}%",
    )


def _transmission_chain(
    result: MarketWatchResult,
    risk_regime: str,
    sentiment_score: Decimal,
) -> list[str]:
    top = _top_mover(result.quotes)
    if top is None:
        return [
            "Fresh cross-asset change data is incomplete.",
            (
                f"Rules-based score stays at {_format_score(sentiment_score)} "
                "until more quotes arrive."
            ),
            "Watch BTC, BTC.D, Nasdaq and S&P 500 before acting.",
        ]
    return [
        (
            f"{top.name} is the strongest impulse: "
            f"{_format_change(top.change, top.change_percent).strip()}"
        ),
        f"Cross-asset score maps that impulse to {risk_regime}.",
        "Watch whether BTC.D confirms concentration or equities confirm broad risk appetite.",
    ]


def _risk_regime(score: Decimal) -> str:
    if score >= Decimal("0.25"):
        return "risk-on"
    if score <= Decimal("-0.25"):
        return "risk-off"
    return "mixed"


def _sentiment_label(score: Decimal) -> str:
    if score >= Decimal("0.10"):
        return "positive"
    if score <= Decimal("-0.10"):
        return "negative"
    return "neutral"


def _average_change(quotes: list[MarketQuote], keys: tuple[str, ...]) -> Decimal | None:
    changes = [
        quote_item.change_percent
        for key in keys
        if (quote_item := _quote_by_key(quotes, key)) is not None
        and quote_item.change_percent is not None
    ]
    if not changes:
        return None
    return sum(changes, Decimal("0")) / Decimal(len(changes))


def _top_mover(quotes: list[MarketQuote]) -> MarketQuote | None:
    movers = [quote_item for quote_item in quotes if quote_item.change_percent is not None]
    if not movers:
        return None
    return max(movers, key=lambda quote_item: abs(quote_item.change_percent or Decimal("0")))


def _quote_by_key(quotes: list[MarketQuote], key: str) -> MarketQuote | None:
    return next((quote_item for quote_item in quotes if quote_item.key == key), None)


def _format_score(score: Decimal) -> str:
    sign = "+" if score > 0 else ""
    return f"{sign}{score.quantize(Decimal('0.01'))}"


def _clamp_decimal(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))
