"""NVD — vulnerabilidades publicadas con puntuación CVSS."""

from __future__ import annotations

from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class NVDVulnerabilities(FeedSource):
    """Monitorea vulnerabilidades de la base de datos nacional de NIST."""

    name: ClassVar[str] = "NVD"
    domain: ClassVar[str] = "cyber"
    event_type: ClassVar[str] = "vulnerability"
    endpoint: ClassVar[str] = "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae CVEs de la respuesta NVD."""
        if not isinstance(payload, dict):
            return []

        vulnerabilities = payload.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            return []

        events = []
        for vuln_entry in vulnerabilities:
            if not isinstance(vuln_entry, dict):
                continue

            cve_data = vuln_entry.get("cve", {})
            if not isinstance(cve_data, dict):
                continue

            cve_id = cve_data.get("id", "").strip()
            if not cve_id:
                continue

            descriptions = cve_data.get("descriptions", [])
            description = ""
            if descriptions and isinstance(descriptions, list):
                for desc_entry in descriptions:
                    if isinstance(desc_entry, dict) and desc_entry.get("lang") == "en":
                        description = desc_entry.get("value", "").strip()
                        break

            metrics = vuln_entry.get("cve", {}).get("metrics", {})
            cvss_v3 = metrics.get("cvssMetricV31") or metrics.get("cvssMetricV30")
            cvss_v2 = metrics.get("cvssMetricV2")

            cvss_score = 0.0
            salience = 0.3
            if cvss_v3 and isinstance(cvss_v3, list) and cvss_v3:
                cvss_obj = cvss_v3[0].get("cvssData", {})
                cvss_score = float(cvss_obj.get("baseScore", 0.0))
                salience = clamp(0.2 + (cvss_score / 10.0 * 0.7))
            elif cvss_v2 and isinstance(cvss_v2, list) and cvss_v2:
                cvss_obj = cvss_v2[0].get("cvssData", {})
                cvss_score = float(cvss_obj.get("baseScore", 0.0))
                salience = clamp(0.2 + (cvss_score / 10.0 * 0.6))

            pub_date = cve_data.get("published")
            if pub_date:
                pub_date = parse_timestamp(pub_date)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{cve_id} (CVSS {cvss_score})",
                    description=description[:500] if description else "Sin descripción",
                    magnitude=cvss_score,
                    salience=salience,
                    event_time=pub_date,
                    external_id=cve_id,
                    raw={
                        "cve_id": cve_id,
                        "cvss_score": round(cvss_score, 1),
                        "published": str(pub_date),
                    },
                )
            )

        return events
