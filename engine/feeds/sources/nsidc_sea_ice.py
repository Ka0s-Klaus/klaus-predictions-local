"""NSIDC Sea Ice Extent — Arctic and Antarctic sea ice monthly data.

From National Snow and Ice Data Center. Tracks polar ice extent as indicator of
climate change and ocean circulation patterns. Low ice extent = high salience signal.
"""

from __future__ import annotations

from typing import ClassVar

import aiohttp

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedError, FeedSource, USER_AGENT


class NSIDCSeaIce(FeedSource):
    """Monthly Arctic and Antarctic sea ice extent from NSIDC."""

    name: ClassVar[str] = "NSIDC"
    domain: ClassVar[str] = "climate"
    event_type: ClassVar[str] = "sea_ice_extent"
    endpoint: ClassVar[str] = "https://nsidc.org/api/seaice_index/data/monthly?format=csv"

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
        """Parse CSV format: Year,Month,Arctic_Extent,Antarctic_Extent,...

        Two events per record: one for Arctic, one for Antarctic.
        Salience based on extent ratio: lower extent = higher salience.
        """
        events = []
        lines = payload.strip().split("\n")
        if not lines:
            return events

        # Track baseline extents for normalization (simplified: use current as proxy)
        baseline_arctic = 7.0  # million km²
        baseline_antarctic = 3.5  # million km²

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or i == 0:  # Skip header
                continue

            parts = line.split(",")
            if len(parts) < 4:
                continue

            try:
                year_str = parts[0].strip()
                month_str = parts[1].strip()
                arctic_extent_str = parts[2].strip()
                antarctic_extent_str = parts[3].strip()

                # Validate numeric fields
                year = int(year_str)
                month = int(month_str)

                if not (1 <= month <= 12):
                    continue

                # Parse extent values (skip if N/A or empty)
                try:
                    arctic_extent = float(arctic_extent_str)
                except ValueError:
                    arctic_extent = None

                try:
                    antarctic_extent = float(antarctic_extent_str)
                except ValueError:
                    antarctic_extent = None

                date_str = f"{year:04d}-{month:02d}-01"
                event_date = parse_timestamp(date_str)
                if event_date is None:
                    continue

                # Create Arctic event if data available
                if arctic_extent is not None and arctic_extent > 0:
                    arctic_ratio = arctic_extent / baseline_arctic
                    arctic_salience = clamp(0.3 + (1.0 - arctic_ratio) * 0.6, 0.3, 1.0)

                    events.append(
                        NormalizedEvent(
                            source=self.name,
                            event_type=self.event_type,
                            title=f"Arctic Sea Ice: {arctic_extent:.2f}M km²",
                            description=f"Arctic sea ice extent for {year}-{month:02d}: {arctic_extent:.2f} million km²",
                            magnitude=arctic_extent,
                            salience=arctic_salience,
                            event_time=event_date,
                            external_id=f"{year:04d}_{month:02d}_arctic",
                            raw={
                                "year": year,
                                "month": month,
                                "region": "arctic",
                                "extent": arctic_extent,
                            },
                        )
                    )

                # Create Antarctic event if data available
                if antarctic_extent is not None and antarctic_extent > 0:
                    antarctic_ratio = antarctic_extent / baseline_antarctic
                    antarctic_salience = clamp(0.3 + (1.0 - antarctic_ratio) * 0.6, 0.3, 1.0)

                    events.append(
                        NormalizedEvent(
                            source=self.name,
                            event_type=self.event_type,
                            title=f"Antarctic Sea Ice: {antarctic_extent:.2f}M km²",
                            description=f"Antarctic sea ice extent for {year}-{month:02d}: {antarctic_extent:.2f} million km²",
                            magnitude=antarctic_extent,
                            salience=antarctic_salience,
                            event_time=event_date,
                            external_id=f"{year:04d}_{month:02d}_antarctic",
                            raw={
                                "year": year,
                                "month": month,
                                "region": "antarctic",
                                "extent": antarctic_extent,
                            },
                        )
                    )
            except (ValueError, IndexError):
                continue

        return events
