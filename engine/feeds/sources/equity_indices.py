"""Equity indices — US market indices from Stooq.

Free data source, no API key required. Provides daily OHLCV data for:
- SPX (S&P 500)
- DJI (Dow Jones Industrial)
- IXIC (Nasdaq)
"""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class EquityIndices(FeedSource):
    """Daily US equity indices from Stooq."""

    name: ClassVar[str] = "Equities"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "equity_index"
    endpoint: ClassVar[str] = "https://stooq.com/q/d/l/?s=^spx,^dji,^ixic&i=d"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Fetch CSV data and parse."""
        headers = {"User-Agent": USER_AGENT, **self.headers}
        try:
            async with session.get(self.endpoint, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise FeedError(f"{self.name}: HTTP {response.status}")
                raw = await response.read()
                if len(raw) > self.max_bytes:
                    raise FeedError(f"{self.name}: response too large")
                text = raw.decode("utf-8", errors="replace")
        except aiohttp.ClientError as exc:
            raise FeedError(f"{self.name}: network error") from exc
        return self.parse(text)

    def parse(self, payload: str) -> list[NormalizedEvent]:
        """Parse CSV format: Symbol,Date,Open,High,Low,Close,Volume"""
        events = []
        lines = payload.strip().split("\n")
        if not lines:
            return events

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or i == 0:  # Skip header
                continue

            parts = line.split(",")
            if len(parts) < 7:
                continue

            try:
                symbol = parts[0].strip()
                date_str = parts[1].strip()
                close_price = float(parts[5].strip())
                volume = parts[6].strip()

                event_date = parse_timestamp(date_str)
                if event_date is None:
                    continue

                # Calculate change percentage (simplified: use magnitude)
                change_pct = 0.0  # Would need prior close, using 0 as default
                salience = clamp(0.4 + (abs(change_pct) / 10), 0.4, 1.0)

                events.append(
                    NormalizedEvent(
                        source=self.name,
                        event_type=self.event_type,
                        title=f"{symbol}: {close_price}",
                        description=f"Closing price for {symbol} on {date_str}",
                        magnitude=close_price,
                        salience=salience,
                        event_time=event_date,
                        external_id=f"{symbol}_{date_str}",
                        raw={
                            "symbol": symbol,
                            "close": close_price,
                            "volume": volume,
                        },
                    )
                )
            except (ValueError, IndexError):
                continue

        return events
