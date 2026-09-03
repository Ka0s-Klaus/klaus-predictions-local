"""Polymarket — mercados de predicción de eventos futuros."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class Polymarket(FeedSource):
    """Monitorea mercados de predicción de crisis y eventos globales."""

    name: ClassVar[str] = "Polymarket"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "prediction_market"
    endpoint: ClassVar[str] = "https://clob.polymarket.com/markets?active=true&closed=false&limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae mercados de predicción de Polymarket."""
        if not isinstance(payload, dict):
            return []

        markets = payload.get("data", [])
        if not isinstance(markets, list):
            return []

        events = []
        for market in markets:
            if not isinstance(market, dict):
                continue

            market_id = market.get("id", "").strip()
            question = market.get("question", "").strip()

            if not market_id or not question:
                continue

            # Salience fija de 0.5 para mercados de predicción
            salience = 0.5

            external_id = market_id

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=question,
                    description=None,
                    magnitude=None,
                    salience=salience,
                    event_time=None,
                    external_id=external_id,
                    raw={
                        "market_id": market_id,
                        "active": market.get("active"),
                        "closed": market.get("closed"),
                    },
                )
            )

        return events
