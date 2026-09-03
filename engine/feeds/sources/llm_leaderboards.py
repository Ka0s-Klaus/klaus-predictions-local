"""LLM Leaderboards — benchmark updates and model performance rankings."""

from __future__ import annotations

import hashlib
from typing import Any, ClassVar

from engine.feeds.normalizer import NormalizedEvent, clamp, parse_timestamp
from engine.feeds.sources.base import FeedSource


class LLMLeaderboards(FeedSource):
    """Monitorea actualizaciones de benchmarks y rankings de LLMs."""

    name: ClassVar[str] = "LLM-Leaderboards"
    domain: ClassVar[str] = "technology"
    event_type: ClassVar[str] = "benchmark_update"
    endpoint: ClassVar[str] = "https://huggingface.co/api/datasets?search=benchmark&limit=20"

    def parse(self, payload: Any) -> list[NormalizedEvent]:
        """Parsea datasets de benchmarks de la API de Hugging Face."""
        events = []

        # Manejo de diferentes formatos
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

            # Extraer nombre del benchmark del ID
            title = dataset.get("title", dataset_id).strip()
            description = dataset.get("description", "").strip() or dataset.get("summary", "").strip()

            updated_at = dataset.get("updated_at")
            created_at = dataset.get("created_at")
            timestamp = updated_at or created_at

            # Downloads como proxy de relevancia
            downloads = dataset.get("downloads", 0)
            if not isinstance(downloads, (int, float)):
                downloads = 0

            # URL del benchmark
            url = f"https://huggingface.co/datasets/{dataset_id}"

            # Generar ID único
            external_id = hashlib.md5(f"{dataset_id}_{timestamp}".encode()).hexdigest()[:16]

            # Salience: 0.7 base, con ajuste por relevancia (downloads)
            salience = clamp(0.7 + min(downloads / 100000.0 * 0.2, 0.2))

            events.append(
                NormalizedEvent(
                    source=self.name,
                    event_type=self.event_type,
                    title=f"{title}",
                    description=description[:500] if description else "LLM benchmark dataset",
                    url=url,
                    magnitude=float(downloads),
                    salience=salience,
                    event_time=parse_timestamp(timestamp),
                    external_id=external_id,
                    raw={
                        "benchmark_id": dataset_id,
                        "downloads": int(downloads),
                        "updated": updated_at,
                    },
                )
            )

        return events
