"""DroughtMonitor — severidad de sequías por estado estadounidense."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class DroughtMonitor(FeedSource):
    """Monitorea severidad de sequías en Estados Unidos."""

    name: ClassVar[str] = "DroughtMonitor"
    domain: ClassVar[str] = "climate"
    event_type: ClassVar[str] = "drought"
    endpoint: ClassVar[str] = "https://droughtmonitor.unl.edu/DmData/TimeSeries.aspx?mode=0&type=1"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Extrae datos de severidad de sequía del Drought Monitor."""
        # Este endpoint puede devolver JSON o CSV/texto dependiendo de parámetros.
        # Intentamos parsear como JSON primero.
        if isinstance(payload, dict):
            # Si es un diccionario, buscar datos de sequía
            data_list = payload.get("data", [])
            if not isinstance(data_list, list):
                return []
        elif isinstance(payload, str):
            # Si es texto, es probablemente CSV. Esperamos formato simple.
            lines = payload.strip().split("\n")
            if len(lines) < 2:
                return []
            data_list = []
            # Parsear CSV básico (simplificado)
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 3:
                    try:
                        data_list.append(
                            {
                                "date": parts[0].strip(),
                                "state": parts[1].strip(),
                                "severity": int(parts[2].strip()),
                            }
                        )
                    except (ValueError, IndexError):
                        continue
        else:
            return []

        events = []
        seen_ids = set()

        for record in data_list:
            if not isinstance(record, dict):
                continue

            date_str = record.get("date", "")
            state = record.get("state", "").strip()
            severity = record.get("severity", 0)

            if not state:
                continue

            try:
                severity = int(severity)
            except (ValueError, TypeError):
                severity = 0

            # Severity escala 0-4: 0=none, 1=abnormal, 2=moderate, 3=severe, 4=extreme
            if severity < 0 or severity > 4:
                severity = 0

            # Salience basada en severidad (0-4 scale)
            salience = clamp(0.3 + (severity / 4.0) * 0.7)

            # Parsear fecha si está disponible
            event_time = None
            if date_str:
                event_time = parse_timestamp(date_str)

            external_id = f"{date_str}_{state}_{severity}".lower().replace(" ", "_")
            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            severity_labels = ["None", "Abnormal", "Moderate", "Severe", "Extreme"]
            severity_label = severity_labels[severity] if 0 <= severity < len(severity_labels) else "Unknown"

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"Drought: {state} — {severity_label}",
                    description=f"Drought severity level {severity}: {severity_label}",
                    magnitude=float(severity),
                    salience=salience,
                    event_time=event_time,
                    external_id=external_id,
                    raw={
                        "state": state,
                        "severity": severity,
                        "severity_label": severity_label,
                    },
                )
            )

        return events
