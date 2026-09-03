"""HackerNews — principales historias de tecnología con puntuaciones."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class HackerNews(FeedSource):
    """Monitorea las historias destacadas de Hacker News."""

    name: ClassVar[str] = "HackerNews"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "tech_news"
    endpoint: ClassVar[str] = "https://hn.algolia.com/api/v1/search?tags=front_page"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae historias destacadas del feed de Hacker News."""
        if not isinstance(payload, dict):
            return []

        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            return []

        events = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue

            title = hit.get("title", "").strip()
            if not title:
                continue

            # Normalizar puntuación (0-100 points → 0.3-1.0 salience)
            points = hit.get("points", 0)
            if isinstance(points, (int, float)):
                salience = clamp(0.3 + (points / 100.0) * 0.7)
            else:
                salience = 0.5

            external_id = hit.get("objectID")
            if not external_id:
                continue

            created_at = hit.get("created_at")
            if created_at:
                created_at = parse_timestamp(created_at)

            url = hit.get("url", "")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=title,
                    description=None,
                    url=url if url else None,
                    magnitude=float(points),
                    salience=salience,
                    event_time=created_at,
                    external_id=str(external_id),
                    raw={
                        "objectID": external_id,
                        "points": points,
                        "author": hit.get("author"),
                    },
                )
            )

        return events
