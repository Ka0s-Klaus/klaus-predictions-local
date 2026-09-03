"""AI Regulation Tracker — AI policy and regulation announcements."""

from __future__ import annotations

import hashlib
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class AIRegulationTracker(FeedSource):
    """Monitorea políticas y regulaciones de IA en fuentes públicas."""

    name: ClassVar[str] = "AI-Regulation-Tracker"
    domain: ClassVar[str] = "policy"
    event_type: ClassVar[str] = "ai_regulation"
    # Usando la API de Hugging Face que expone datasets de regulación
    # Fallback: podría ser https://www.brookings.edu/.../artificial-intelligence/
    endpoint: ClassVar[str] = "https://huggingface.co/api/datasets?search=regulation&limit=10"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Parsea información de regulación de IA."""
        events = []

        # Manejo de diferentes formatos de respuesta
        if isinstance(payload, dict):
            datasets = payload.get("datasets", [])
        elif isinstance(payload, list):
            datasets = payload
        else:
            return []

        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue

            dataset_id = dataset.get("id", "").strip()
            if not dataset_id:
                continue

            title = dataset.get("title", dataset_id).strip()
            description = dataset.get("description", "").strip() or dataset.get("summary", "").strip()

            updated_at = dataset.get("updated_at")
            created_at = dataset.get("created_at")
            timestamp = updated_at or created_at

            # URL del dataset
            url = f"https://huggingface.co/datasets/{dataset_id}"

            # Generar ID único
            external_id = hashlib.md5(dataset_id.encode()).hexdigest()[:16]

            # Salience alta para políticas de IA
            salience = clamp(0.85)

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"AI Regulation Dataset: {title}",
                    description=description[:500] if description else "AI regulation and policy dataset",
                    url=url,
                    salience=salience,
                    event_time=parse_timestamp(timestamp),
                    external_id=external_id,
                    raw={
                        "dataset_id": dataset_id,
                        "url": url,
                        "updated": updated_at,
                    },
                )
            )

        return events
