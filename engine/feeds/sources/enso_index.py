"""ENSO Index — El Niño/Southern Oscillation indicator from NOAA.

The Oceanic Niño Index (ONI) is the primary indicator for El Niño and La Niña episodes.
Values > 0.5 indicate El Niño (warming), < -0.5 indicate La Niña (cooling).
High salience during transitions between states (strong signal).
"""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class ENSOIndex(FeedSource):
    """Monthly Oceanic Niño Index from NOAA Climate Prediction Center."""

    name: ClassVar[str] = "ENSO"
    domain: ClassVar[str] = "climate"
    event_type: ClassVar[str] = "climate_oscillation"
    endpoint: ClassVar[str] = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedEvent]:
        """Fetch NOAA fixed-width text data."""
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
        """Parse fixed-width NOAA format with Year, Month, ONI_index columns.

        Lines starting with spaces or # are headers/comments and are skipped.
        """
        events = []
        lines = payload.strip().split("\n")
        if not lines:
            return events

        for line in lines:
            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith(" " * 5):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            try:
                year_str = parts[0].strip()
                month_str = parts[1].strip()
                oni_str = parts[2].strip()

                # Validate numeric fields
                year = int(year_str)
                month = int(month_str)
                oni_index = float(oni_str)

                if not (1 <= month <= 12):
                    continue

                # Create date (use day 1 of the month)
                date_str = f"{year:04d}-{month:02d}-01"
                event_date = parse_timestamp(date_str)
                if event_date is None:
                    continue

                # Salience based on ONI magnitude: high values (El Niño/La Niña) = high salience
                salience = clamp(0.3 + abs(oni_index / 2.5), 0.3, 1.0)

                # Determine event classification based on ONI
                if oni_index > 0.5:
                    title = f"El Niño (ONI: {oni_index})"
                elif oni_index < -0.5:
                    title = f"La Niña (ONI: {oni_index})"
                else:
                    title = f"Neutral (ONI: {oni_index})"

                events.append(
                    NormalizedEvent(
                        source=self.name,
                        event_type=self.event_type,
                        title=title,
                        description=f"Oceanic Niño Index for {year}-{month:02d}: {oni_index}",
                        magnitude=oni_index,
                        salience=salience,
                        event_time=event_date,
                        external_id=f"{year:04d}_{month:02d}",
                        raw={
                            "year": year,
                            "month": month,
                            "oni_index": oni_index,
                        },
                    )
                )
            except (ValueError, IndexError):
                continue

        return events
