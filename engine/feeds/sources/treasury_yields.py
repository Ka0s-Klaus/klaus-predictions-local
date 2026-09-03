"""Treasury yields — US Treasury yield curve data.

Data from Treasury Department. Tracks changes in 10-year yield as a proxy for
interest rate expectations and bond market sentiment. Updated daily on business days.
"""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class TreasuryYields(FeedSource):
    """Daily US Treasury yield curve rates."""

    name: ClassVar[str] = "Treasury"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "yield_curve"
    endpoint: ClassVar[str] = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/daily-treasury-yield-curve-rates-data"
    )

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Fetch Treasury data."""
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
        """Parse CSV format: Date,1mo,3mo,6mo,1yr,2yr,5yr,10yr,30yr"""
        events = []
        lines = payload.strip().split("\n")
        if not lines:
            return events

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or i == 0:  # Skip header
                continue

            parts = line.split(",")
            if len(parts) < 8:
                continue

            try:
                date_str = parts[0].strip()
                yield_10yr_str = parts[7].strip()  # 10-year is column 7

                if not yield_10yr_str or yield_10yr_str.lower() == "n/a":
                    continue

                yield_10yr = float(yield_10yr_str)
                event_date = parse_timestamp(date_str)
                if event_date is None:
                    continue

                # Calculate change in basis points (simplified: use yield magnitude)
                change_bps = abs(yield_10yr * 100)
                salience = clamp(0.5 + (change_bps / 100), 0.5, 1.0)

                events.append(
                    NormalizedEvent(
                        source=self.name,
                        event_type=self.event_type,
                        title=f"10Y Yield: {yield_10yr}%",
                        description=f"US Treasury 10-year yield on {date_str}",
                        magnitude=yield_10yr,
                        salience=salience,
                        event_time=event_date,
                        external_id=f"treasury_{date_str}",
                        raw={
                            "date": date_str,
                            "yield_10yr": yield_10yr,
                        },
                    )
                )
            except (ValueError, IndexError):
                continue

        return events
