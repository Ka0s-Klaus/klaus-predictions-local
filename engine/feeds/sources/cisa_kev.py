"""CISA-KEV — vulnerabilidades cibernéticas con explotación confirmada.

Sin clave de API. El feed JSON es público y estable.
Se actualiza cuando se reporta una nuevo uso en la práctica, típicamente
varias veces al mes. Una ola de nuevas explotaciones en corto tiempo
señala una campaña de ataque o una reacción en cadena.
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, parse_timestamp
from engine.feeds.sources.base import FeedSource


class CISAKEVulnerabilities(FeedSource):
    """Vulnerabilidades del catálogo CISA de explotaciones confirmadas."""

    name: ClassVar[str] = "CISA-KEV"
    domain: ClassVar[str] = "cyber"
    event_type: ClassVar[str] = "kev_exploit"
    endpoint: ClassVar[str] = (
        "https://www.cisa.gov/sites/default/files/feeds/"
        "known_exploited_vulnerabilities.json"
    )

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """El payload es {'vulnerabilities': [...]}."""
        events = []
        vulnerabilities = payload.get("vulnerabilities", [])

        for vuln in vulnerabilities:
            cve_id = vuln.get("cveID", "")
            if not cve_id:
                continue

            description = vuln.get("vulnDescription", "")
            date_added = vuln.get("dateAdded", "")

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{cve_id}: {description[:60]}",
                    magnitude=1.0,
                    salience=0.9,  # Muy alto: son explotaciones reales
                    external_id=cve_id,
                    event_time=parse_timestamp(date_added),
                    raw=vuln,
                )
            )

        return events
