"""Divisas — tipos de cambio de referencia del BCE vía Frankfurter.

Sin clave de API. El BCE publica una vez al día en días laborables, así que en
fin de semana el dato es el del viernes: es correcto, no está obsoleto.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource

# Divisas que importan para el análisis macro; el resto son ruido aquí.
WATCHED = ("EUR", "JPY", "GBP", "CNY", "CHF", "RUB", "TRY", "INR", "BRL", "MXN")


class ForexRates(FeedSource):
    """Tipos de cambio frente al dólar."""

    name: ClassVar[str] = "Forex"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "fx_rate"
    endpoint: ClassVar[str] = "https://api.frankfurter.dev/v1/latest?base=USD"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        rates = payload.get("rates") or {}
        date = parse_timestamp(payload.get("date"))
        base = payload.get("base", "USD")

        events = []
        for currency in WATCHED:
            rate = rates.get(currency)
            if rate is None:
                continue
            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{base}/{currency} = {rate}",
                    description=f"Tipo de referencia del BCE para {base}/{currency}",
                    magnitude=float(rate),
                    # Un tipo de cambio no es un evento: es contexto. Relevancia
                    # baja y constante para que no desplace a los sucesos reales.
                    salience=clamp(0.35),
                    event_time=date,
                    external_id=f"{base}{currency}:{payload.get('date')}",
                    raw={"base": base, "quote": currency, "rate": rate},
                )
            )
        return events
