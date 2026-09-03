"""EDGAR — operaciones de insiders en el mercado de valores."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class EDGARInsider(FeedSource):
    """Monitorea operaciones de insiders reportadas a la SEC."""

    name: ClassVar[str] = "EDGAR"
    domain: ClassVar[str] = "markets"
    event_type: ClassVar[str] = "insider_trade"
    endpoint: ClassVar[str] = 'https://efts.sec.gov/LATEST/search-index?q=%22Form+4%22'

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae filings de Form 4 de EDGAR."""
        # EDGAR puede devolver diferentes formatos. Esperamos JSON.
        if isinstance(payload, dict):
            # Buscar el array de hits o resultados
            results = payload.get("hits", payload.get("results", []))
            if not isinstance(results, list):
                return []
        else:
            return []

        events = []
        for filing in results:
            if not isinstance(filing, dict):
                continue

            # Extraer información básica del filing
            filing_id = filing.get("id", "").strip()
            if not filing_id:
                filing_id = filing.get("accession_number", "").strip()

            if not filing_id:
                continue

            company = filing.get("company_name", "").strip()
            if not company:
                company = filing.get("company", "").strip()

            # Extraer información de la transacción
            transaction_value = filing.get("transaction_value")
            if transaction_value is None:
                transaction_value = filing.get("value")

            try:
                transaction_value = float(transaction_value) if transaction_value else 0.0
            except (ValueError, TypeError):
                transaction_value = 0.0

            # Salience basada en tamaño de transacción
            if transaction_value > 0:
                salience = clamp(0.4 + min(transaction_value / 1000000.0, 0.6))
            else:
                salience = 0.3

            # Parsear fecha
            filing_date = filing.get("filing_date", filing.get("date"))
            if filing_date:
                filing_date = parse_timestamp(filing_date)

            external_id = filing_id

            insider_name = filing.get("insider_name", "").strip()
            if not insider_name:
                insider_name = "Unknown Insider"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{company} — Insider Filing by {insider_name}",
                    description=f"Form 4 filing: Transaction value ${transaction_value:,.0f}",
                    magnitude=transaction_value,
                    salience=salience,
                    event_time=filing_date,
                    external_id=external_id,
                    raw={
                        "filing_id": filing_id,
                        "company": company,
                        "insider": insider_name,
                        "transaction_value": round(transaction_value, 2),
                    },
                )
            )

        return events
