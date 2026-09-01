"""Cripto — precios y variación a 24 h vía CoinGecko.

Sin clave de API, pero con límite de peticiones: unas 10-30 por minuto en el
plan gratuito. Con el intervalo de 15 minutos por defecto sobra de largo.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp
from engine.feeds.sources.base import FeedSource

COINS = ("bitcoin", "ethereum", "solana", "tether")

# Una variación diaria de esta magnitud ya es una señal de estrés del mercado.
SIGNIFICANT_MOVE_PCT = 10.0


class CryptoPrices(FeedSource):
    """Precios en dólares y su variación en las últimas 24 horas."""

    name: ClassVar[str] = "Crypto"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "crypto_price"
    endpoint: ClassVar[str] = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={','.join(COINS)}&vs_currencies=usd&include_24hr_change=true"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        events = []
        for coin, data in payload.items():
            price = data.get("usd")
            if price is None:
                continue
            change = data.get("usd_24h_change")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{coin.upper()} ${price:,.2f}" + self._suffix(change),
                    magnitude=float(price),
                    salience=self._salience(change),
                    external_id=coin,
                    raw={"coin": coin, "usd": price, "change_24h": change},
                )
            )
        return events

    @staticmethod
    def _suffix(change: float | None) -> str:
        return f" ({change:+.2f}% 24h)" if change is not None else ""

    @staticmethod
    def _salience(change: float | None) -> float:
        """Un precio estable no informa; un desplome sí."""
        if change is None:
            return 0.3
        return clamp(0.3 + min(abs(change) / SIGNIFICANT_MOVE_PCT, 1.0) * 0.5)
