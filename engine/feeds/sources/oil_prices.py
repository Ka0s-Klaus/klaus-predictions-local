"""Oil prices — Crude futures from Stooq.

Tracks WTI Crude Light and Brent Crude futures prices. Used as leading indicators
for energy markets and economic activity. High volatility periods signal market stress.
"""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class OilPrices(FeedSource):
    """Daily crude oil futures prices from Stooq."""

    name: ClassVar[str] = "Oil"
    domain: ClassVar[str] = "commodities"
    event_type: ClassVar[str] = "commodity_price"
    endpoint: ClassVar[str] = "https://stooq.com/q/d/l/?s=cl.f,bz.f&i=d"

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

                # Map symbol to commodity name
                if symbol.upper().startswith("CL"):
                    commodity = "WTI Crude"
                elif symbol.upper().startswith("BZ"):
                    commodity = "Brent Crude"
                else:
                    commodity = symbol

                # Calculate change percentage (simplified: use magnitude)
                change_pct = 0.0  # Would need prior close, using 0 as default
                salience = clamp(0.4 + (abs(change_pct) / 5), 0.4, 1.0)

                events.append(
                    NormalizedEvent(
                        source=self.name,
                        event_type=self.event_type,
                        title=f"{commodity}: ${close_price}/bbl",
                        description=f"Closing price for {commodity} ({symbol}) on {date_str}",
                        magnitude=close_price,
                        salience=salience,
                        event_time=event_date,
                        external_id=f"{commodity.replace(' ', '_').lower()}_{date_str}",
                        raw={
                            "symbol": symbol,
                            "commodity": commodity,
                            "close": close_price,
                            "volume": volume,
                        },
                    )
                )
            except (ValueError, IndexError):
                continue

        return events
